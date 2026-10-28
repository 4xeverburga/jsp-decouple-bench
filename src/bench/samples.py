"""The samples: the code under test, and the behaviour being graded.

Inspect gives every Sample a fresh sandbox and the sandbox is the stack, so
a sample cannot be the code alone — every case of a manifest would then share
one database, and the goldens were captured on a pristine one.

What identifies it is the CODE, not the task: a manifest is already fixed by
the task you invoked, so folding its id into the sample says nothing. The
case is the one thing that must appear, because it is what makes two samples
of the same commit distinct.

    id        mamute@7f4a0e55:vote-flow__upvote-increments-count
              project slug, commit, behaviour — a score can be quoted from it
    metadata  project_id, branch, commit, case, manifest, task type
    input     the work order (read when solving, unused when scoring)

`sandbox` is bound at the Task, so it stays out of here.
"""

from inspect_ai.dataset import Sample

from .seeds import manifest as load_manifest
from .seeds import pin, source, work_order


def code_id(slug: str, commit: str) -> str:
    """The code under test: which project, at which commit."""
    return f"{slug}@{commit[:8]}"


def _metadata(chosen: dict, commit: str) -> dict:
    record = source(chosen["source"])
    return {
        "project_id": record["project_id"],
        "branch": record["branch"],
        "slug": record["slug"],
        "commit": commit,
        "manifest": chosen["name"],
        "task_type": chosen["task_type"],
    }


def for_scoring(manifest_id: int) -> list[Sample]:
    """One sample per case, each against the pinned commit."""
    chosen = load_manifest(manifest_id)
    commit = pin(chosen["source"])
    code = code_id(chosen["source"], commit)
    base = _metadata(chosen, commit)
    return [
        Sample(
            id=f"{code}:{case}",
            input=work_order(chosen),
            target="decoupled",
            metadata=dict(base, manifest_id=manifest_id, case=case),
        )
        for case in chosen["scope"]["cases"]
    ]


def for_solving(manifest_id: int, run: str) -> list[Sample]:
    """One sample for the manifest: the agent works on the tree once."""
    chosen = load_manifest(manifest_id)
    base = _metadata(chosen, pin(chosen["source"]))
    return [
        Sample(
            id=f"{code_id(chosen['sample'], run)}:{chosen['name']}",
            input=work_order(chosen),
            target="decoupled",
            metadata=dict(base, manifest_id=manifest_id, run=run),
        )
    ]
