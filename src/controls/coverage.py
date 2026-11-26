"""Code coverage of a manifest's cases: see this package's README.md."""

import asyncio
import bisect
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
from src.core.cases import db
from src.core.cases.cases import drive
from src.core.compose import scoring_compose
from src.core.observe import arrange
from src.core.seeds import sample
from src.core.stack import running


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
    target: db.Target,
) -> Path:
    """Play one case on a stack of its own and keep its coverage XML."""
    layer = out / f"{case}.compose.yaml"
    service = override(slug, includes, home, layer)
    _say(f"{case}: starting a stack with the coverage agent")
    async with running(slug, (layer,)) as stack:
        await arrange(stack, slug, case, target)
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
    """One controller's methods and lines from a case's XML.

    Each executable line is given to the method it sits in: the one whose
    first line is the nearest above it. Lambdas are not boundaries, so
    their lines stay with the method that holds them.
    """
    root = ET.parse(xml).getroot()
    package = controller.rpartition(".")[0]
    node = root.find(f".//package[@name='{package.replace('.', '/')}']")
    if node is None:
        raise RuntimeError(f"{xml.name}: no package {package}")
    clazz = node.find(f"class[@name='{controller.replace('.', '/')}']")
    if clazz is None:
        raise RuntimeError(f"{xml.name}: no class {controller}")
    executed: set[str] = set()
    starts: list[tuple[int, str]] = []
    for method in clazz.findall("method"):
        name = method.get("name")
        if name.startswith("lambda$"):
            continue
        if method.get("line"):
            starts.append((int(method.get("line")), name))
        covered, _total = _counters(method).get("INSTRUCTION", (0, 0))
        if covered > 0 and not name.startswith("<"):
            executed.add(name)
    starts.sort()
    source = node.find(f"sourcefile[@name='{clazz.get('sourcefilename')}']")
    lines = {}
    for line in source.findall("line") if source is not None else []:
        nr = int(line.get("nr"))
        if int(line.get("mi")) + int(line.get("ci")) == 0:
            continue
        at = bisect.bisect_right(starts, (nr, "￿")) - 1
        lines[nr] = {
            "method": starts[at][1] if at >= 0 else None,
            "covered": int(line.get("ci")) > 0,
            "branches": int(line.get("mb")) + int(line.get("cb")),
            "covered_branches": int(line.get("cb")),
        }
    return {"executed": sorted(executed), "lines": lines}


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


def _tally(lines: list[dict]) -> dict:
    return {
        "LINE": [sum(line["covered"] for line in lines), len(lines)],
        "BRANCH": [
            sum(line["covered_branches"] for line in lines),
            sum(line["branches"] for line in lines),
        ],
    }


def _union(cases: list[dict]) -> dict[int, dict]:
    lines: dict[int, dict] = {}
    for one_case in cases:
        for nr, line in one_case["lines"].items():
            kept = lines.setdefault(nr, dict(line, covered=False))
            kept["covered"] = kept["covered"] or line["covered"]
            kept["covered_branches"] = max(
                kept["covered_branches"], line["covered_branches"]
            )
    return lines


def _coverage(lines: dict[int, dict], wanted: list[str]) -> dict:
    return {
        "slice": _tally(
            [line for line in lines.values() if line["method"] in wanted]
        ),
        "controller": _tally(list(lines.values())),
    }


def _status(name: str, claim: dict, by: list[str]) -> str:
    if name not in claim["slice"]:
        return "outside the slice"
    if name in claim["handlers"]:
        return "verified" if claim["handlers"][name] in by else "NOT EXECUTED"
    if name in claim["not_driven"]:
        return "not driven (excused)"
    return "executed, unclaimed" if by else "GAP"


def assess(claim: dict, found: list[str], measured: dict[str, dict]) -> dict:
    """Cross one controller's claim with its source and its execution."""
    rows = []
    for name in found:
        by = sorted(c for c, m in measured.items() if name in m["executed"])
        rows.append(
            {
                "handler": name,
                "in_slice": name in claim["slice"],
                "claimed_by": claim["handlers"].get(name),
                "executed_by": by,
                "status": _status(name, claim, by),
                "reason": claim["not_driven"].get(name),
            }
        )
    named = set(claim["slice"]) | set(claim["handlers"])
    named |= set(claim["not_driven"])
    stale = sorted(named - set(found))
    stale += sorted(
        (set(claim["handlers"]) | set(claim["not_driven"]))
        - set(claim["slice"])
        - set(stale)
    )
    driven = sum(row["status"] == "verified" for row in rows)
    return {
        "handlers": rows,
        "stale_claims": stale,
        "handler_coverage": [driven, len(claim["slice"])],
        "cases": {
            case: _coverage(one_case["lines"], claim["slice"])
            for case, one_case in measured.items()
        },
        "union": _coverage(_union(list(measured.values())), claim["slice"]),
    }


def report(
    manifest: dict,
    controllers: dict[str, dict],
    apps: dict[str, list[int]],
    out: Path,
) -> Path:
    """Write `report.json` and `report.md` for one manifest."""
    summary = {
        "manifest": manifest["name"],
        "sample": manifest["sample"],
        "controllers": controllers,
        "app_lines": apps,
    }
    (out / "report.json").write_text(json.dumps(summary, indent=2) + "\n")
    target = out / "report.md"
    target.write_text(markdown(summary))
    return target


def markdown(summary: dict) -> str:
    """Render a `report.json` summary as the tables of `report.md`."""
    controllers = summary["controllers"]
    driven = sum(c["handler_coverage"][0] for c in controllers.values())
    total = sum(c["handler_coverage"][1] for c in controllers.values())
    md = [
        f"# Coverage — `{summary['manifest']}` ({summary['sample']})",
        "",
        "## 1. Handler coverage (claim vs. execution)",
        "",
        f"**{driven}/{total} slice handlers driven and verified.**",
    ]
    for name, assessed in controllers.items():
        rows = [
            [
                f"`{row['handler']}`",
                "yes" if row["in_slice"] else "",
                row["claimed_by"] or "—",
                ", ".join(row["executed_by"]) or "—",
                row["status"]
                + (f" — {row['reason']}" if row["reason"] else ""),
            ]
            for row in sorted(
                assessed["handlers"], key=lambda row: not row["in_slice"]
            )
        ]
        md += [
            "",
            f"### `{name}`",
            "",
            tabulate(
                rows,
                ["handler", "slice", "claimed by", "executed by", "status"],
                tablefmt="github",
            ),
        ]
        if assessed["stale_claims"]:
            md += [
                "",
                "Claims naming no handler of the source or of the slice: "
                f"{assessed['stale_claims']}",
            ]
    md += [
        "",
        "## 2. Line and branch coverage (JaCoCo, per case)",
        "",
        "Slice = the lines of the slice's handlers; controller = the whole "
        "source file. Branches over several cases are a lower bound.",
    ]
    for name, assessed in controllers.items():
        rows = [
            [
                case,
                _percent(cov["slice"]["LINE"]),
                _percent(cov["slice"]["BRANCH"]),
                _percent(cov["controller"]["LINE"]),
                _percent(cov["controller"]["BRANCH"]),
            ]
            for case, cov in [
                *assessed["cases"].items(),
                ("**all cases**", assessed["union"]),
            ]
        ]
        md += [
            "",
            f"### `{name.rpartition('.')[2]}`",
            "",
            tabulate(
                rows,
                [
                    "case",
                    "slice lines",
                    "slice branches",
                    "controller lines",
                    "controller branches",
                ],
                tablefmt="github",
            ),
        ]
    md += [
        "",
        "App lines executed per case: "
        + ", ".join(
            f"{case} {_percent(pair)}"
            for case, pair in summary["app_lines"].items()
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
            f"controllers and their slice before measuring them"
        )
    slug = manifest["sample"]
    claims = covers["controllers"]
    first = next(iter(claims))
    # Only the app's own classes are instrumented: the sample names them.
    includes = ":".join(f"{root}.*" for root in sample(slug)["code_packages"])
    found = {name: handlers(tree, name) for name in claims}
    home = tools()
    out = settings.COVERAGE / manifest["name"]
    out.mkdir(parents=True, exist_ok=True)
    target = db.Target.from_options(manifest["bindings"]["db"]["options"])
    xmls = {
        case: asyncio.run(
            one(slug, case, first, includes, home, out, target)
        )
        for case in cases
    }
    written = summarize(manifest, claims, found, xmls, out)
    _say(f"wrote {written.relative_to(settings.ROOT)}")
    return written


def summarize(
    manifest: dict,
    claims: dict[str, dict],
    found: dict[str, list[str]],
    xmls: dict[str, Path],
    out: Path,
) -> Path:
    """Report from the XML each case left, without starting a stack."""
    controllers = {
        name: assess(
            claim,
            found[name],
            {case: measure(xml, name) for case, xml in xmls.items()},
        )
        for name, claim in claims.items()
    }
    apps = {
        case: list(_counters(ET.parse(xml).getroot()).get("LINE", (0, 0)))
        for case, xml in xmls.items()
    }
    return report(manifest, controllers, apps, out)
