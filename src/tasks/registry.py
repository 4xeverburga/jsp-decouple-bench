"""src/tasks/registry.py — task_type name → implementation.

Mirrors the TASK_TYPE table: adding a task type means a seed row plus one
package here.
"""
from __future__ import annotations

import importlib
from typing import Any

from src.errors import NotFound
from src.tasks.ports import TaskInputPort

CATALOG: dict[str, tuple[str, str]] = {
    "decouple_slice": ("src.tasks.decouple_slice.run", "RUNNER"),
    "oneshot_decoupling": ("src.tasks.oneshot_decoupling.run", "RUNNER"),
}


def resolve(task_type: str) -> TaskInputPort:
    if task_type not in CATALOG:
        raise NotFound(
            f"no implementation for task_type '{task_type}'. "
            f"known: {sorted(CATALOG)}"
        )
    module_name, attr = CATALOG[task_type]
    runner: Any = getattr(importlib.import_module(module_name), attr)
    return runner
