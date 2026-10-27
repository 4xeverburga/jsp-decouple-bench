"""decouple_slice — one feature boundary.

The manifest's scope is authoritative: only the cases listed there are
replayed. Everything outside the boundary may stay server-rendered.
"""
from __future__ import annotations

from src.tasks.base import BaseTask


class DecoupleSliceTask(BaseTask):
    name = "decouple_slice"

    def scope(self, ctx):
        scope = dict(ctx.scope)
        scope["cases"] = list(scope.get("cases") or [])
        return scope


RUNNER = DecoupleSliceTask()
