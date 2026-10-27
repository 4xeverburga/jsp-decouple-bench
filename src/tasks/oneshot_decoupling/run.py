"""oneshot_decoupling — the whole sample in one run.

Scope is every case the sample has. The manifest's own case list is kept
for reporting, but the task widens it, which is the point of "oneshot".
"""
from __future__ import annotations

from src.tasks.base import BaseTask


class OneShotDecouplingTask(BaseTask):
    name = "oneshot_decoupling"

    def scope(self, ctx):
        scope = dict(ctx.scope)
        discovered = sorted(
            p.parent.name for p in ctx.cases_dir.glob("*/case.json")
        )
        declared = list(scope.get("cases") or [])
        scope["cases"] = discovered
        if declared and set(declared) != set(discovered):
            scope["widened_from"] = declared
        return scope


RUNNER = OneShotDecouplingTask()
