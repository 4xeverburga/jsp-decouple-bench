"""The samples: the code under test, and the behaviour being graded.

The scorer starts a fresh stack for every Sample, so a sample cannot be the
code alone — every case of a manifest would then share one database, and the
goldens were captured on a pristine one.

What identifies it is the CODE, not the task: a manifest is already fixed by
the task you invoked, so folding its id into the sample says nothing. The
case is the one thing that must appear, because it is what makes two samples
of the same commit distinct.

    id        mamute@7f4a0e55:vote-flow__upvote-increments-count
              project slug, commit, behaviour — a score can be quoted from it
    metadata  project_id, branch, commit, case, manifest, task type
    input     the work order (read when solving, unused when scoring)
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


def for_solving(
    manifest_id: int,
    run: str,
    agent: str,
    agent_model: str,
    agent_version: str,
    model_target: str,
) -> list[Sample]:
    """One sample for the manifest: the agent works on the tree once.

    The agent trio is recorded, not used: it names what ran, the version of
    it, and the model name it asked the bridge for. `model_target` is what
    actually answered, and it is what a score has to be attributed to — the
    wire name is only the format of the request.
    """
    chosen = load_manifest(manifest_id)
    commit = pin(chosen["source"])
    return [
        Sample(
            id=f"{code_id(chosen['source'], commit)}:{chosen['name']}",
            input=work_order(chosen),
            target="decoupled",
            metadata=dict(
                _metadata(chosen, commit),
                manifest_id=manifest_id,
                run=run,
                agent=agent,
                agent_model=agent_model,
                agent_version=agent_version,
                model_target=model_target,
            ),
        )
    ]
