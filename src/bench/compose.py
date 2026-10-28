"""Preparing source Compose for Inspect and comparing declared topology.

`compose config` resolves substitution, override files, `external:` and
`name:` without starting anything, so this costs milliseconds and cannot be
confused by an app that fails to boot.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import yaml

from . import settings
from .seeds import pin
from .seeds import source as source_record


def render(compose: Path) -> dict:
    run = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(compose),
            "config",
            "--format",
            "json",
        ],
        cwd=compose.parent,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(run.stdout)


def sandbox_compose(slug: str, checkout: str) -> Path:
    """Prepare the source's Compose file for Inspect without changing it."""
    record = source_record(slug)
    stack = record.get("stack")
    if not stack:
        raise ValueError(f"source {slug!r} has no stack configuration")

    compose_file = Path(checkout) / stack["compose_file"]
    if not compose_file.is_file():
        raise FileNotFoundError(
            f"Compose file for source {slug!r} not found: {compose_file}"
        )

    config = yaml.safe_load(compose_file.read_text())
    service = stack["default_service"]
    services = config.get("services") or {}
    if service not in services:
        raise ValueError(
            f"default service {service!r} is not defined in {compose_file}"
        )
    services[service]["x-default"] = True

    generated = compose_file.with_name(".bench-inspect-compose.yaml")
    generated.write_text(yaml.safe_dump(config, sort_keys=False))
    return generated


def networks(rendered: dict, service: str) -> set[str]:
    spec = (rendered.get("services") or {}).get(service) or {}
    return set(spec.get("networks") or {})


def ports(rendered: dict, service: str) -> set[str]:
    spec = (rendered.get("services") or {}).get(service) or {}
    published: set[str] = set()
    for entry in spec.get("ports") or []:
        if isinstance(entry, dict) and entry.get("published") is not None:
            published.add(str(entry["published"]))
        elif isinstance(entry, str) and ":" in entry:
            published.add(entry.split(":")[-2])
    return published


def escaped(mode: str) -> bool:
    """A service that left the project's own networks."""
    return mode == "host" or mode.startswith("service:")


def contract_and_submission(slug: str) -> tuple[dict, dict]:
    """The pin's shape, and the tree's — never the tree's claim alone."""
    pinned = f"{pin(slug)}:compose.yaml"
    blob = subprocess.run(
        ["git", "-C", settings.checkout(), "show", pinned],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    scratch = Path(tempfile.mkdtemp())
    pinned = scratch / "compose.yaml"
    pinned.write_text(blob)
    return render(pinned), render(Path(settings.checkout()) / "compose.yaml")
