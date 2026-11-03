"""A case's spans, reduced to the shape a decoupling changes.

The collector writes OTLP JSON: one line per export batch, a thousand spans
for one flow, most of them ids, timestamps and the app's own startup. What
a decoupling changes is narrower — which requests the browser made, and
under each one whether the work ran in-process (SQL straight under the
page's span) or behind an HTTP hop to the app itself (a client span, the
backend's server span under it, the SQL under that). This module keeps
exactly that, deterministically, so the golden and a submission are cut
the same way and the judge reads a tree, not a dump.

    {"label": "SERVER POST /answer/{n} -> 302", "count": 1, "children": [
        {"label": "HTTP CLIENT POST /api/questions/{n}/answers -> 201", ...

Ids, timestamps, hosts and numbers in paths are erased; identical siblings
are folded into one node with a count. Static assets are dropped: they are
served by the container, never by a controller.
"""

import json
import re
from pathlib import Path

SERVER = 2
CLIENT = 3

# A request the browser made for a file, not for a page or an action.
STATIC = re.compile(
    r"\.(?:css|js|png|gif|jpe?g|svg|ico|woff2?|ttf|eot|map)$", re.IGNORECASE
)
# Wrappers that only re-say what their children say: an ORM call is the SQL
# under it, a commit is the statements before it.
LIFTED_SCOPES = ("io.opentelemetry.hibernate",)
# What a JDBC driver asks a fresh connection, on every request: not the
# app's work, and identical on both sides of any change.
DRIVER_NOISE = re.compile(
    r"^\s*(?:/\*.*?\*/\s*)?(?:SHOW\b|SELECT\s+@@)", re.IGNORECASE | re.DOTALL
)
# The stack's healthcheck: every sample's app service is probed with curl
# (`src/samples/<slug>/env/compose.yaml`), every few seconds, during the
# flow too. Not the app's work, and it lands inside browser requests by
# chance, so it is told apart by who sent it, not by when.
PROBE = re.compile(r"^curl/")
TABLE = re.compile(r"\b(?:from|into|update)\s+([A-Za-z_][\w.]*)", re.I)


def _value(raw: dict):
    (value,) = raw.values()
    return value


def _attributes(span: dict) -> dict:
    return {a["key"]: _value(a["value"]) for a in span.get("attributes", [])}


def _path(text: str) -> str:
    """A path with its numbers and slugs erased, so two runs compare."""
    text = re.sub(r"/\d+-[^/?]+", "/{n}-{slug}", text)
    return re.sub(r"\d+", "{n}", text)


def _sql(attrs: dict) -> str | None:
    """`SQL <operation> <table>`, or None for the driver's own chatter.

    The table comes from the statement: the span's name only carries the
    database's name for anything with a join.
    """
    statement = attrs.get("db.statement", "")
    if DRIVER_NOISE.match(statement):
        return None
    operation = attrs.get("db.operation") or statement.split(" ")[0].upper()
    found = TABLE.search(statement)
    table = attrs.get("db.sql.table") or (found.group(1) if found else "")
    return f"SQL {operation} {table.split('.')[-1]}".rstrip()


def _label(span: dict, attrs: dict) -> str | None:
    status = attrs.get("http.response.status_code")
    method = attrs.get("http.request.method")
    if span["kind"] == SERVER:
        label = f"SERVER {method} {_path(attrs['url.path'])} -> {status}"
        route = attrs.get("http.route", "")
        if route.endswith(".jsp"):
            label += f" renders {route}"
        return label
    if span["kind"] == CLIENT and "db.system" in attrs:
        return _sql(attrs)
    if span["kind"] == CLIENT and "url.full" in attrs:
        path = re.sub(r"^[a-z]+://[^/]+", "", attrs["url.full"])
        return f"HTTP CLIENT {method} {_path(path.split('?')[0])} -> {status}"
    return span["name"]


def read(path: Path) -> list[dict]:
    """Every span in a collector file, with its scope name beside it."""
    spans = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        batch = json.loads(line)
        for resource in batch["resourceSpans"]:
            for scope in resource["scopeSpans"]:
                for span in scope["spans"]:
                    spans.append(dict(span, scope=scope["scope"]["name"]))
    return spans


def _fold(nodes: list[dict]) -> list[dict]:
    """Fold runs of identical siblings into one node with a count."""
    folded: list[dict] = []
    for node in nodes:
        last = folded[-1] if folded else None
        if (
            last is not None
            and last["label"] == node["label"]
            and last["children"] == node["children"]
        ):
            last["count"] += node["count"]
        else:
            folded.append(node)
    return folded


def _window(span: dict) -> tuple[int, int]:
    return int(span["startTimeUnixNano"]), int(span["endTimeUnixNano"])


def _origin(span: dict) -> str:
    return _attributes(span).get("client.address", "")


def _enclosing(span: dict, roots: list[dict]) -> dict | None:
    """The other-origin root this one ran inside, if it ran inside one.

    A request that arrives from a different address while a browser request
    is still being served, and is over before it, was made by serving that
    request: a hop whose client sent no trace context, so it has no client
    span to hang from.
    """
    start, end = _window(span)
    for other in roots:
        if other is span or _origin(other) == _origin(span):
            continue
        outer_start, outer_end = _window(other)
        if outer_start <= start and end <= outer_end:
            return other
    return None


def condense(spans: list[dict]) -> list[dict]:
    """The browser's requests, in order, each with what served it.

    A root is a server span with no parent: a request from outside the app.
    A server span whose parent is the app's own client span is the backend
    answering a loopback call, so it stays nested where it happened. A root
    that ran inside a request from another address is nested under it too,
    labelled `UNTRACED HOP`. The stack's healthcheck (`PROBE`) is dropped
    wherever it landed.
    """
    by_id = {span["spanId"]: span for span in spans}
    children: dict[str, list[dict]] = {}
    for span in spans:
        parent = span.get("parentSpanId")
        if parent and parent in by_id:
            children.setdefault(parent, []).append(span)

    candidates = [
        span
        for span in spans
        if span["kind"] == SERVER
        and span.get("parentSpanId") not in by_id
        and not STATIC.search(_attributes(span).get("url.path", ""))
        and not PROBE.match(_attributes(span).get("user_agent.original", ""))
    ]
    roots: list[dict] = []
    adopted: set[str] = set()
    for span in candidates:
        outer = _enclosing(span, candidates)
        if outer is not None:
            children.setdefault(outer["spanId"], []).append(span)
            adopted.add(span["spanId"])
        else:
            roots.append(span)

    def build(span: dict) -> list[dict]:
        below = sorted(
            children.get(span["spanId"], []),
            key=lambda child: int(child["startTimeUnixNano"]),
        )
        nested = [node for child in below for node in build(child)]
        if span["scope"].startswith(LIFTED_SCOPES):
            return nested
        label = _label(span, _attributes(span))
        if label is None:
            return nested
        if span["spanId"] in adopted:
            label = f"UNTRACED HOP {label}"
        return [{"label": label, "count": 1, "children": _fold(nested)}]

    roots.sort(key=lambda span: int(span["startTimeUnixNano"]))
    return [node for root in roots for node in build(root)]


def render(nodes: list[dict]) -> str:
    """The tree as indented text, the form the judge reads."""
    lines: list[str] = []

    def walk(level: list[dict], depth: int) -> None:
        for node in level:
            times = f" x{node['count']}" if node["count"] > 1 else ""
            lines.append(f"{'  ' * depth}{node['label']}{times}")
            walk(node["children"], depth + 1)

    walk(nodes, 0)
    return "\n".join(lines)


def loopback_calls(nodes: list[dict]) -> int:
    """How many requests the app made to itself while serving another.

    An HTTP client call answered by the app's own server span, or a hop
    that arrived with no client span (`UNTRACED HOP`).
    """
    count = 0
    for node in nodes:
        answered = node["label"].startswith("HTTP CLIENT") and any(
            child["label"].startswith("SERVER") for child in node["children"]
        )
        if answered or node["label"].startswith("UNTRACED HOP"):
            count += node["count"]
        count += loopback_calls(node["children"])
    return count
