"""functional_parity/artifacts.py — make browser artifacts replayable.

Artifacts come from a live stack, so they contain values that belong to
*this* run rather than to the behaviour being graded:

- the base URL — host ports are allocated per run, so a golden captured on
  one port could never match a run on another;
- absolute timestamps of the rows the flow created;
- a build stamp in a footer (revision + build time): every case rebuilds the
  image, so it changes every run and says nothing about behaviour;
- bare calendar dates, which legacy forms prefill from the host clock (a
  form opened today shows today's date, so the markup would only match on
  the day it was captured);
- inline `style` attributes, which page scripts rewrite through the CSSOM
  (`width: 100%;`) or leave exactly as the server wrote them
  (`width:100%`), depending on whether they ran before the snapshot.

`normalize` reduces all three to a fixed form. Capture and replay both pass
through it, so a golden and the value it is compared against are reduced in
exactly the same way.
"""

from __future__ import annotations

import re
from typing import Any

BASE_URL_TOKEN = "{{base_url}}"
TIMESTAMP_TOKEN = "{{timestamp}}"
DATE_TOKEN = "{{date}}"
BUILD_TOKEN = "{{build}}"

_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
)
# A revision plus the moment it was built — what a footer stamp renders
# (`Changeset: a9ddda25ceca 2026-10-30 05:33 +0000`). Every case rebuilds the
# image, so this value can never be part of a golden: it is provenance, not
# behaviour.
_BUILD_RE = re.compile(
    r"\b[0-9a-f]{7,40}\s+\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}"
    r"(?::\d{2})?\s*[+-]\d{4}\b"
)
# A bare calendar date — `2026-10-30` or the `30-Oct-2026` a legacy form
# prefills from the host clock. Replaced after the timestamps, so an ISO
# datetime becomes one token, not a token with a date inside it. Values the
# behaviour actually owns are asserted by the DB delta, which keeps them
# exact.
_DATE_RE = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}-[A-Z][a-z]{2}-\d{4})\b")
_STYLE_ATTR_RE = re.compile(r'(\s+)style="([^"]*)"')


def _canonical_style(match: re.Match[str]) -> str:
    declarations = []
    for part in match.group(2).split(";"):
        part = part.strip()
        if not part:
            continue
        prop, _, value = part.partition(":")
        declarations.append(f"{prop.strip()}:{value.strip()}")
    if not declarations:
        return ""
    return match.group(1) + 'style="' + ";".join(declarations) + '"'


def _normalize(value: Any, base_url: str) -> Any:
    if isinstance(value, str):
        text = value.replace(base_url, BASE_URL_TOKEN)
        text = _BUILD_RE.sub(BUILD_TOKEN, text)
        text = _TIMESTAMP_RE.sub(TIMESTAMP_TOKEN, text)
        text = _DATE_RE.sub(DATE_TOKEN, text)
        return _STYLE_ATTR_RE.sub(_canonical_style, text)
    if isinstance(value, dict):
        return {key: _normalize(item, base_url) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item, base_url) for item in value]
    return value


def normalize(artifacts: dict[str, Any], base_url: str) -> dict[str, Any]:
    """Return `artifacts` with every run-specific value replaced."""
    return {
        key: _normalize(value, base_url) for key, value in artifacts.items()
    }
