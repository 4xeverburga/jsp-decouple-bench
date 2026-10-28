"""src/harness/registry.py — harness name → implementation.

The harness is chosen per **run**, not per sample: comparing agents is the
point, so it must not live in the manifest. The chosen name is recorded in
`TASK_RUN.harness`.
"""

from __future__ import annotations

import importlib
from typing import Any

from src.errors import NotFoundError
from src.harness.ports import HarnessPort

CATALOG: dict[str, tuple[str, str]] = {
    "command": ("src.harness.adapters.command", "CommandHarness"),
    "claude-code": ("src.harness.adapters.presets", "ClaudeCodeHarness"),
    "opencode": ("src.harness.adapters.presets", "OpenCodeHarness"),
    "pi": ("src.harness.adapters.presets", "PiHarness"),
}


def names() -> list[str]:
    return sorted(CATALOG)


def resolve(name: str, options: dict[str, Any] | None = None) -> HarnessPort:
    if name not in CATALOG:
        raise NotFoundError(f"unknown harness '{name}'. known: {names()}")
    module_name, class_name = CATALOG[name]
    cls = getattr(importlib.import_module(module_name), class_name)
    return cls(options or {})
