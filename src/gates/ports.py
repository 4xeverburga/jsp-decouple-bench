"""src/gates/ports.py — what a gate must implement.

A gate measures a run and returns a GateResult. It never writes to the DB
and never talks to another gate: gates are independent and unordered.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class GateInputPort(Protocol):
    gate_id: str

    def evaluate(self) -> Any:
        """Return `src.run.results.GateResult`."""
