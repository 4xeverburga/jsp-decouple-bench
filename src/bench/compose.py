"""Reading a stack's declared shape: the pin's, and the submission's.

`compose config` resolves substitution, override files, `external:` and
`name:` without starting anything, so this costs milliseconds and cannot be
confused by an app that fails to boot.
"""

import json
import subprocess
import tempfile
from pathlib import Path

from . import settings
from .seeds import pin


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
