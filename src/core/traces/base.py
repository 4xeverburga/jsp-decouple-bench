"""A case's trace base: the spans the pristine pin produced, condensed.

It sits beside `expect.json` as `trace.json` and is written by the same
`capture` that freezes the golden, from the same run of the flow. What is
frozen is the condensed tree (`spans.condense`), not the collector's file:
that is a megabyte of ids and timestamps for one flow, and the tree is what
both sides are compared as. Changing how spans are condensed therefore
means capturing the bases again — the same rule as the artifact normalizer.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import settings

from . import spans


def path(slug: str, case: str) -> Path:
    return settings.SAMPLES / slug / "cases" / case / "trace.json"


def freeze(slug: str, case: str, commit: str, collected: Path) -> Path:
    """Condense a capture's spans and write them as the case's base."""
    requests = spans.condense(spans.read(collected))
    if not requests:
        raise RuntimeError(
            f"{case}: the capture's spans hold no request from the browser; "
            f"is the OpenTelemetry agent running? ({collected})"
        )
    target = path(slug, case)
    base = {
        "sample": slug,
        "case": case,
        "sample_commit": commit,
        # Provenance, never compared, as in `expect.json`.
        "captured_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        ),
        "requests": requests,
    }
    target.write_text(json.dumps(base, indent=2) + "\n")
    return target


def read(slug: str, case: str) -> list[dict]:
    """The frozen tree. Missing is an error: there is nothing to compare."""
    found = path(slug, case)
    if not found.is_file():
        raise FileNotFoundError(
            f"{case} has no trace base ({found}); run "
            f"`main.py capture` for its manifest first"
        )
    return json.loads(found.read_text())["requests"]
