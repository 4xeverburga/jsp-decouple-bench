"""src/tasks/registry.py — task_type name → runner.

Both rows of `TASK_TYPE` share one implementation; what differs is the
manifest's case scope. An unknown name is a seed error, not a code path.
"""
from __future__ import annotations

from src.errors import NotFound
from src.tasks.base import Task

TASK_TYPES = frozenset({"decouple_slice", "oneshot_decoupling"})


def resolve(task_type: str) -> Task:
    if task_type not in TASK_TYPES:
        raise NotFound(f"unknown task_type '{task_type}'. known: {sorted(TASK_TYPES)}")
    return Task(task_type)
