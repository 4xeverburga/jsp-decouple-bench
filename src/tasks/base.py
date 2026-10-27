"""src/tasks/base.py — the task implementation.

There is exactly one: `decouple_slice` and `oneshot_decoupling` differ only
in the manifest's case scope, which is data. A task's job is to assert the
pinned checkout, snapshot the diff and record what the run will be graded
on — it never starts the stack and never applies an agent's edits.
"""
from __future__ import annotations

from src.run import RunContext
from src.run.atomic import write_json, write_text
from src.run.results import utcnow
from src.run.sample_checkout import diff, ensure_pinned


class Task:
    def __init__(self, name: str):
        self.name = name

    def prepare(self, ctx: RunContext) -> None:
        sample = ctx.sample
        preconditions = ensure_pinned(
            ctx.sample_location, sample["commit_sha"], sample.get("entrypoint")
        )

        patch = diff(ctx.sample_location, sample["commit_sha"])
        write_text(ctx.paths.diff_patch, patch)

        write_json(ctx.paths.task_json, {
            "run_id": ctx.run_id,
            "manifest_id": ctx.manifest["manifest_id"],
            "manifest_version": ctx.manifest["version"],
            "task_type": ctx.manifest["task_type"],
            "prompt": ctx.manifest["prompt"],
            "sample": {**sample, "location": preconditions["location"]},
            "technologies": ctx.manifest.get("sample_technologies", []),
            "bindings": ctx.bindings,
            "scope": ctx.scope,
            "preconditions": preconditions,
            "started_at": utcnow(),
            "diff": {
                "path": str(ctx.paths.diff_patch),
                "bytes": len(patch),
                "empty": not patch.strip(),
            },
        })
