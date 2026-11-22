"""Code coverage of a manifest's cases: see this package's README.md."""

import asyncio
import hashlib
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml
from tabulate import tabulate

import settings
from src.bench.compose import scoring_compose
from src.bench.scorers.functional_parity.cases import drive
from src.bench.seeds import sample
from src.bench.stack import running


def _say(line: str) -> None:
    print(f"[coverage] {line.rstrip()}", file=sys.stderr, flush=True)


def _fetch(url: str, target: Path, sha256: str) -> None:
    if target.exists() and _digest(target) == sha256:
        return
    _say(f"fetching {url}")
    with urllib.request.urlopen(url) as answer:
        payload = answer.read()
    if hashlib.sha256(payload).hexdigest() != sha256:
        raise RuntimeError(f"{url} does not match its pinned sha256")
    target.write_bytes(payload)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tools() -> Path:
    """The directory holding the pinned JaCoCo agent and CLI."""
    version = settings.JACOCO_VERSION
    home = settings.TOOLS / f"jacoco-{version}"
    home.mkdir(parents=True, exist_ok=True)
    _fetch(
        f"{settings.JACOCO_REPOSITORY}/org.jacoco.agent/{version}/"
        f"org.jacoco.agent-{version}-runtime.jar",
        home / "jacocoagent.jar",
        settings.JACOCO_AGENT_SHA256,
    )
    _fetch(
        f"{settings.JACOCO_REPOSITORY}/org.jacoco.cli/{version}/"
        f"org.jacoco.cli-{version}-nodeps.jar",
        home / "jacococli.jar",
        settings.JACOCO_CLI_SHA256,
    )
    return home


def jvm_hook(slug: str) -> tuple[str, str, str]:
    """The service, variable and value that load the OTel agent.

    Every sample attaches its tracing agent through the app's own
    launcher variable (`CATALINA_OPTS`, `MAVEN_OPTS`); the coverage agent
    rides on the same one, so it lands in the JVM that hosts the app.
    """
    compose = yaml.safe_load(scoring_compose(slug).read_text())
    for name, service in compose["services"].items():
        for key, value in service.get("environment", {}).items():
            if isinstance(value, str) and settings.OTEL_AGENT_FLAG in value:
                return name, key, value
    flag = settings.OTEL_AGENT_FLAG
    raise RuntimeError(f"{slug}: no service sets {flag} in its environment")


def override(slug: str, includes: str, home: Path, target: Path) -> str:
    """Write the compose override that attaches JaCoCo; return the service."""
    service, key, value = jvm_hook(slug)
    agent = (
        f"-javaagent:{settings.JACOCO_MOUNT}/jacocoagent.jar="
        f"output=tcpserver,address={settings.JACOCO_ADDRESS},"
        f"port={settings.JACOCO_PORT},"
        f"includes={includes}"
    )
    target.write_text(
        yaml.safe_dump(
            {
                "services": {
                    service: {
                        "environment": {key: f"{value} {agent}"},
                        "volumes": [
                            f"{home}:{settings.JACOCO_MOUNT}:ro",
                        ],
                    }
                }
            },
            sort_keys=False,
        )
    )
    return service


async def _in(stack, service: str, script: str) -> str:
    done = await stack.exec(service, ["sh", "-c", script], "")
    if done.returncode != 0:
        raise RuntimeError(
            f"{service}: `{script}` failed: {done.stderr.strip()}"
        )
    return done.stdout


async def _classes_root(stack, service: str, controller: str) -> str:
    """The directory the image compiled the app's classes into.

    Found from the controller's own class file, because samples differ:
    `target/classes`, or `WEB-INF/classes` when the pom compiles there.
    A WAR build leaves a second copy in its exploded directory; JaCoCo
    refuses two classes of one name, so the shortest path wins.
    """
    relative = controller.replace(".", "/") + ".class"
    found = (
        await _in(
            stack,
            service,
            f"find {settings.IMAGE_WORKDIR} -path '*/{relative}'",
        )
    ).split()
    if not found:
        raise RuntimeError(f"{service}: no {relative} under the workdir")
    return min((path[: -len(relative) - 1] for path in found), key=len)


async def one(
    slug: str,
    case: str,
    controller: str,
    includes: str,
    home: Path,
    out: Path,
) -> Path:
    """Play one case on a stack of its own and keep its coverage XML."""
    layer = out / f"{case}.compose.yaml"
    service = override(slug, includes, home, layer)
    _say(f"{case}: starting a stack with the coverage agent")
    async with running(slug, (layer,)) as stack:
        _artifacts, shot = await asyncio.to_thread(
            drive, slug, case, stack.base_url
        )
        if shot:
            (settings.ROOT / shot).unlink(missing_ok=True)
        cli = f"java -jar {settings.JACOCO_MOUNT}/jacococli.jar"
        dump = settings.JACOCO_DUMP_DIR
        root = await _classes_root(stack, service, controller)
        dirs = f"--classfiles {root}"
        await _in(
            stack,
            service,
            f"mkdir -p {dump} && {cli} dump --quiet "
            f"--address {settings.JACOCO_ADDRESS} "
            f"--port {settings.JACOCO_PORT} "
            f"--destfile {dump}/case.exec && "
            f"{cli} report --quiet {dump}/case.exec {dirs} "
            f"--xml {dump}/case.xml",
        )
        for suffix in ("exec", "xml"):
            kept = out / f"{case}.{suffix}"
            if not stack.copy_out(service, f"{dump}/case.{suffix}", kept):
                raise RuntimeError(f"{case}: could not copy case.{suffix}")
    _say(f"{case}: kept {out / case}.xml")
    return out / f"{case}.xml"


def _counters(node: ET.Element) -> dict:
    return {
        counter.get("type"): (
            int(counter.get("covered")),
            int(counter.get("missed")) + int(counter.get("covered")),
        )
        for counter in node.findall("counter")
    }


def measure(xml: Path, controller: str) -> dict:
    """The controller's methods and lines, and the app's totals, from XML."""
    root = ET.parse(xml).getroot()
    package, _, simple = controller.rpartition(".")
    wanted = controller.replace(".", "/")
    node = root.find(f".//package[@name='{package.replace('.', '/')}']")
    if node is None:
        raise RuntimeError(f"{xml.name}: no package {package}")
    clazz = node.find(f"class[@name='{wanted}']")
    if clazz is None:
        raise RuntimeError(f"{xml.name}: no class {controller}")
    methods: dict[str, dict] = {}
    for method in clazz.findall("method"):
        name = method.get("name")
        if name.startswith("<") or name.startswith("lambda$"):
            continue
        covered, total = _counters(method).get("INSTRUCTION", (0, 0))
        seen = methods.setdefault(name, {"covered": 0, "total": 0})
        seen["covered"] += covered
        seen["total"] += total
    source = node.find(f"sourcefile[@name='{clazz.get('sourcefilename')}']")
    lines = {
        int(line.get("nr")): {
            "covered": int(line.get("ci")) > 0,
            "branches": int(line.get("mb")) + int(line.get("cb")),
            "covered_branches": int(line.get("cb")),
        }
        for line in (source.findall("line") if source is not None else [])
        if int(line.get("mi")) + int(line.get("ci")) > 0
    }
    return {
        "class": _counters(clazz),
        "app": _counters(root),
        "methods": methods,
        "lines": lines,
        "simple_name": simple,
    }


HANDLER = re.compile(
    r"^\s*(?:@\w+(?:\([^)]*\))?\s*)*(?:public|protected)\s+"
    r"(?!class\b|interface\b|static\b)"
    r"(?:final\s+|synchronized\s+)*[\w<>\[\],.? ]+?\s+(\w+)\s*\(",
    re.M,
)
ACCESSOR = re.compile(r"^(get|set|is)[A-Z]")


def handlers(tree: Path, controller: str) -> list[str]:
    """The controller's public and protected instance methods, in order."""
    relative = Path(*controller.split(".")).with_suffix(".java")
    found = [p for p in tree.rglob(relative.name) if p.match(str(relative))]
    if len(found) != 1:
        raise RuntimeError(f"{controller}: {len(found)} sources in the pin")
    text = found[0].read_text(encoding="utf-8", errors="replace")
    simple = controller.rpartition(".")[2]
    names: list[str] = []
    for match in HANDLER.finditer(text):
        name = match.group(1)
        # Bean accessors are how a Struts action receives its form, not
        # routes of their own.
        if ACCESSOR.match(name):
            continue
        if name != simple and name not in names:
            names.append(name)
    return names


def _percent(pair: tuple[int, int]) -> str:
    covered, total = pair
    if total == 0:
        return "n/a"
    return f"{100 * covered / total:.0f}% ({covered}/{total})"


def _union(measured: dict[str, dict]) -> dict:
    lines: dict[int, dict] = {}
    for one_case in measured.values():
        for nr, line in one_case["lines"].items():
            kept = lines.setdefault(
                nr,
                {
                    "covered": False,
                    "branches": line["branches"],
                    "covered_branches": 0,
                },
            )
            kept["covered"] = kept["covered"] or line["covered"]
            kept["covered_branches"] = max(
                kept["covered_branches"], line["covered_branches"]
            )
    return {
        "LINE": (
            sum(line["covered"] for line in lines.values()),
            len(lines),
        ),
        "BRANCH": (
            sum(line["covered_branches"] for line in lines.values()),
            sum(line["branches"] for line in lines.values()),
        ),
    }


def report(
    manifest: dict, found: list[str], measured: dict[str, dict], out: Path
) -> Path:
    """Cross the manifest's claim with what the cases executed."""
    covers = manifest["scope"]["covers"]
    claimed = covers["handlers"]
    excused = covers["not_driven"]
    executed = {
        name: sorted(
            case
            for case, one_case in measured.items()
            if one_case["methods"].get(name, {"covered": 0})["covered"] > 0
        )
        for name in found
    }
    rows = []
    for name in found:
        by = executed[name]
        if name in claimed:
            status = "verified" if claimed[name] in by else "NOT EXECUTED"
        elif name in excused:
            status = "not driven (excused)"
        elif by:
            status = "executed, unclaimed"
        else:
            status = "GAP"
        rows.append(
            {
                "handler": name,
                "claimed_by": claimed.get(name),
                "executed_by": by,
                "status": status,
                "reason": excused.get(name),
            }
        )
    stale = sorted((set(claimed) | set(excused)) - set(found))
    driven = sum(row["status"] == "verified" for row in rows)
    union = _union(measured)
    summary = {
        "manifest": manifest["name"],
        "sample": manifest["sample"],
        "controller": covers["controller"],
        "handlers": rows,
        "stale_claims": stale,
        "handler_coverage": [driven, len(found)],
        "cases": {
            case: {
                "controller_lines": one_case["class"].get("LINE"),
                "controller_branches": one_case["class"].get("BRANCH"),
                "app_lines": one_case["app"].get("LINE"),
                "methods_executed": sorted(
                    name
                    for name, method in one_case["methods"].items()
                    if method["covered"] > 0
                ),
            }
            for case, one_case in measured.items()
        },
        "union": {"LINE": union["LINE"], "BRANCH": union["BRANCH"]},
    }
    (out / "report.json").write_text(json.dumps(summary, indent=2) + "\n")
    target = out / "report.md"
    target.write_text(markdown(summary))
    return target


def markdown(summary: dict) -> str:
    """Render a `report.json` summary as the two tables of `report.md`."""
    handler_rows = [
        [
            f"`{row['handler']}`",
            row["claimed_by"] or "—",
            ", ".join(row["executed_by"]) or "—",
            row["status"] + (f" — {row['reason']}" if row["reason"] else ""),
        ]
        for row in summary["handlers"]
    ]
    case_rows = [
        [
            case,
            _percent(row["controller_lines"] or (0, 0)),
            _percent(row["controller_branches"] or (0, 0)),
            _percent(row["app_lines"] or (0, 0)),
        ]
        for case, row in summary["cases"].items()
    ]
    union = summary["union"]
    case_rows.append(
        [
            "**all cases**",
            _percent(union["LINE"]),
            f"{_percent(union['BRANCH'])} (lower bound)",
            "—",
        ]
    )
    driven, total = summary["handler_coverage"]
    md = [
        f"# Coverage — `{summary['manifest']}` ({summary['sample']})",
        "",
        f"Controller: `{summary['controller']}`",
        "",
        "## 1. Handler coverage (claim vs. execution)",
        "",
        f"**{driven}/{total} handlers driven and verified.**",
        "",
        tabulate(
            handler_rows,
            ["handler", "claimed by", "executed by", "status"],
            tablefmt="github",
        ),
    ]
    if summary["stale_claims"]:
        md += [
            "",
            "Claims naming no handler of the source: "
            f"{summary['stale_claims']}",
        ]
    md += [
        "",
        "## 2. Line and branch coverage (JaCoCo, per case)",
        "",
        tabulate(
            case_rows,
            ["case", "controller lines", "controller branches", "app lines"],
            tablefmt="github",
        ),
        "",
    ]
    return "\n".join(md)


def run(manifest: dict, cases: list[str], tree: Path) -> Path:
    """Measure every named case of one manifest, one stack each."""
    covers = manifest["scope"].get("covers")
    if covers is None:
        raise SystemExit(
            f"manifest {manifest['id']} declares no scope.covers: name its "
            f"controller and map its handlers before measuring them"
        )
    slug = manifest["sample"]
    controller = covers["controller"]
    # Only the app's own classes are instrumented: the sample names them.
    includes = ":".join(f"{root}.*" for root in sample(slug)["code_packages"])
    found = handlers(tree, controller)
    home = tools()
    out = settings.COVERAGE / manifest["name"]
    out.mkdir(parents=True, exist_ok=True)
    measured = {}
    for case in cases:
        xml = asyncio.run(one(slug, case, controller, includes, home, out))
        measured[case] = measure(xml, controller)
    written = report(manifest, found, measured, out)
    _say(f"wrote {written.relative_to(settings.ROOT)}")
    return written
