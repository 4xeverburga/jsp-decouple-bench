"""The seeds: what a slice is, and the work order a run receives."""

import json

import settings


def _seed(name: str) -> list[dict]:
    return json.loads((settings.SEEDS / name).read_text())


def task_type(kind: str) -> dict:
    for candidate in _seed("task_types.json"):
        if candidate["name"] == kind:
            return candidate
    raise KeyError(kind)


def manifest(manifest_id: int) -> dict:
    """A manifest by the id the seeds give it.

    The id is the bench's unit of work: it names a sample, a slice, a task
    type and the cases that slice is graded against.
    """
    for candidate in _seed("manifests.json"):
        if candidate["id"] == manifest_id:
            return candidate
    raise KeyError(f"no manifest with id {manifest_id}")


def manifests() -> list[dict]:
    return _seed("manifests.json")


def source(slug: str) -> dict:
    """The registry row for a code source: provenance and the pin."""
    for row in _seed("sources.json"):
        if row["slug"] == slug:
            return row
    raise KeyError(slug)


def pin(slug: str) -> str:
    for row in _seed("sources.json"):
        if row["slug"] == slug:
            return row["commit_sha"]
    raise KeyError(slug)


def work_order(chosen: dict) -> str:
    """The two data fields the agent reads — no routes, no case names."""
    kind = task_type(chosen["task_type"])
    solve = source(chosen["source"]).get("solve", {})
    try:
        base = kind["base_prompt"].format(**solve)
    except KeyError as missing:
        raise ValueError(
            f"source {chosen['source']!r} has no solve {missing.args[0]!r}"
        ) from None
    return f"{base.rstrip()}\n\n{chosen['prompt'].rstrip()}\n"
