"""src/harness/registry.py — `"mysql@1"` → adapter class.

Adapters are keyed by TECHNOLOGY, never by sample: `mysql@1` serves every
sample whose manifest binds it. Which adapter a run uses is data
(`TASK_MANIFEST.bindings_json`), not control flow.
"""
from __future__ import annotations

import importlib
from typing import Any

from src.errors import UnknownAdapter

# adapter id -> (capability, module, class)
CATALOG: dict[str, tuple[str, str, str]] = {
    "compose@1":    ("stack",   "src.harness.adapters.compose.stack", "ComposeStack"),
    "playwright@1": ("browser", "src.harness.adapters.playwright.browser", "PlaywrightBrowser"),
    "mysql@1":      ("db",      "src.harness.adapters.mysql.db", "MysqlDatabase"),
    "postgres@1":   ("db",      "src.harness.adapters.postgres.db", "PostgresDatabase"),
    "h2@1":         ("db",      "src.harness.adapters.h2.db", "H2Database"),
    "shell@1":      ("db",      "src.harness.adapters.shell.db", "ShellDatabase"),
}


def capabilities() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for adapter, (capability, _, _) in CATALOG.items():
        out.setdefault(capability, []).append(adapter)
    return out


def resolve(ctx: Any, capability: str) -> Any:
    binding = ctx.binding(capability)
    adapter_id = binding.get("adapter")
    if not adapter_id:
        raise UnknownAdapter(f"binding '{capability}' has no 'adapter' key: {binding}")
    if adapter_id not in CATALOG:
        raise UnknownAdapter(
            f"unknown adapter {adapter_id!r} for capability '{capability}'. "
            f"known adapters: {sorted(CATALOG)}"
        )
    declared, module_name, class_name = CATALOG[adapter_id]
    if declared != capability:
        raise UnknownAdapter(
            f"adapter {adapter_id!r} provides '{declared}', not '{capability}'"
        )
    module = importlib.import_module(module_name)
    try:
        cls = getattr(module, class_name)
    except AttributeError:  # pragma: no cover - catalog/config error
        raise UnknownAdapter(f"{module_name} has no class {class_name}") from None
    return cls(ctx, binding.get("options") or {})
