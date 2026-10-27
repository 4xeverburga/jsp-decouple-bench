"""src/tasks/ports.py — what a task type must implement."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class TaskResult:
    run_id: str
    manifest_id: int
    task_type: str
    preconditions: dict[str, Any] = field(default_factory=dict)
    scope: dict[str, Any] = field(default_factory=dict)
    diff_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "manifest_id": self.manifest_id,
            "task_type": self.task_type,
            "preconditions": self.preconditions,
            "scope": self.scope,
            "diff_bytes": self.diff_bytes,
        }


@runtime_checkable
class TaskInputPort(Protocol):
    name: str

    def prepare(self, ctx: Any) -> TaskResult:
        """Assert preconditions, snapshot the tree, write task.json.

        Does not apply an agent's edits and does not start the stack: the
        gates decide whether the result is a decoupling.
        """
