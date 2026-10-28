"""src/tasks/base.py — the task implementation.

There is exactly one: `decouple_slice` and `oneshot_decoupling` differ only
in the manifest's case scope, which is data.

A task fills the prompt, hands it to the **harness** (the agent, or the
thing driving one), and records what came back. It never starts the stack
and never edits the sample itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.harness.ports import HarnessPort, HarnessResult, HarnessTask
from src.run import RunContext
from src.run.atomic import write_json, write_text
from src.run.results import utcnow
from src.run.sample_checkout import diff, ensure_pinned


class Task:
    def __init__(self, name: str):
        self.name = name

    def prepare(self, ctx: RunContext, harness: HarnessPort) -> HarnessResult:
        sample = ctx.sample
        preconditions = ensure_pinned(
            ctx.sample_location, sample["commit_sha"], sample.get("entrypoint")
        )
        scope = ctx.scope

        filled = HarnessTask(
            prompt=ctx.manifest["prompt"],
            cwd=Path(preconditions["location"]),
        )
        result = harness.run(filled, ctx.paths.root)

        # The diff comes from git, never from the harness's own claims.
        patch = diff(ctx.sample_location, sample["commit_sha"])
        harness_doc: dict[str, Any] = {
            "harness": harness.name,
            **result.to_dict(),
            "diff_bytes": len(patch),
            "diff_empty": not patch.strip(),
        }
        write_text(ctx.paths.diff_patch, patch)
        write_json(ctx.paths.harness, harness_doc)
        write_json(
            ctx.paths.task_json,
            {
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
                "harness": harness_doc,
                "started_at": utcnow(),
            },
        )
        return result
