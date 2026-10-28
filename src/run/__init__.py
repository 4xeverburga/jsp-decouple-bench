"""src/run/__init__.py — run-scoped primitives (no orchestration here)."""

from __future__ import annotations

from src.run.context import RunContext
from src.run.ids import new_run_id
from src.run.net import allocate as allocate_ports
from src.run.paths import RunPaths
from src.run.results import CaseResult, GateResult, utcnow

__all__ = [
    "RunContext",
    "RunPaths",
    "CaseResult",
    "GateResult",
    "new_run_id",
    "allocate_ports",
    "utcnow",
]
