"""src/tasks/base.py — the shared half of every task type.

A task's `prepare` is always: assert the pinned checkout, snapshot the
worktree diff, write `out/runs/<run_id>/task.json`. Subclasses only decide
what `scope` means for them.
"""
from __future__ import annotations

from typing import Any

from src.run import RunContext
from src.run.atomic import write_json, write_text
from src.run.results import utcnow
from src.run.sample_checkout import diff, ensure_pinned
from src.tasks.ports import TaskResult


class BaseTask:
    name = "base"

    def scope(self, ctx: RunContext) -> dict[str, Any]:
        return dict(ctx.scope)

    def prepare(self, ctx: RunContext) -> TaskResult:
        sample = ctx.sample
        preconditions = ensure_pinned(
            ctx.sample_location, sample["commit_sha"], sample.get("entrypoint")
        )

        patch = diff(ctx.sample_location, sample["commit_sha"])
        write_text(ctx.paths.diff_patch, patch)

        scope = self.scope(ctx)
        started_at = utcnow()
        write_json(ctx.paths.task_json, {
            "run_id": ctx.run_id,
            "manifest_id": ctx.manifest["manifest_id"],
            "manifest_version": ctx.manifest["version"],
            "task_type": ctx.manifest["task_type"],
            "prompt": ctx.manifest["prompt"],
            "sample": {**sample, "location": preconditions["location"]},
            "technologies": ctx.manifest.get("sample_technologies", []),
            "bindings": ctx.bindings,
            "scope": scope,
            "preconditions": preconditions,
            "started_at": started_at,
            "diff": {
                "path": str(ctx.paths.diff_patch),
                "bytes": len(patch),
                "empty": not patch.strip(),
            },
        })

        return TaskResult(
            run_id=ctx.run_id,
            manifest_id=ctx.manifest["manifest_id"],
            task_type=ctx.manifest["task_type"],
            preconditions=preconditions,
            scope=scope,
            diff_bytes=len(patch),
        )
