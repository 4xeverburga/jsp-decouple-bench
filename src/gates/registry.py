"""src/gates/registry.py — gate_id → implementation.

v1 ships three gates, and only these three: `functional_parity`,
`network_isolation`, `trace_similarity`. More will be added; a gate needs a
seed row in `seeds/gates.json` plus a directory here.
"""
from __future__ import annotations

import importlib
from typing import Any

from src.errors import NotFound
from src.gates.ports import GateInputPort

CATALOG: dict[str, tuple[str, str]] = {
    "functional_parity": ("src.gates.functional_parity.eval", "FunctionalParity"),
    "network_isolation": ("src.gates.network_isolation.eval", "NetworkIsolation"),
    "trace_similarity": ("src.gates.trace_similarity.eval", "TraceSimilarity"),
}


def resolve(ctx: Any, definition: dict[str, Any]) -> GateInputPort:
    gate_id = definition["gate_id"]
    if gate_id not in CATALOG:
        raise NotFound(
            f"no implementation for gate '{gate_id}'. known: {sorted(CATALOG)}"
        )
    module_name, class_name = CATALOG[gate_id]
    cls = getattr(importlib.import_module(module_name), class_name)
    return cls(ctx, definition)
