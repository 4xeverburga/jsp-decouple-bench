"""functional_parity/artifacts.py — make browser artifacts replayable.

Artifacts come from a live stack, so they contain values that belong to
*this* run rather than to the behaviour being graded:

- the base URL — host ports are allocated per run, so a golden captured on
  one port could never match a run on another;
- absolute timestamps of the rows the flow created;
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

_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
)
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
        text = _TIMESTAMP_RE.sub(TIMESTAMP_TOKEN, text)
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
