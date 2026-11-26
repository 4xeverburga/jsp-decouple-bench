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


def sample(slug: str) -> dict:
    """The registry row for a sample: provenance and the pin."""
    for row in _seed("samples.json"):
        if row["slug"] == slug:
            return row
    raise KeyError(slug)


def pin(slug: str) -> str:
    for row in _seed("samples.json"):
        if row["slug"] == slug:
            return row["commit_sha"]
    raise KeyError(slug)


def _prompt(kind: str, name: str) -> str:
    """A prompt from `seeds/prompts/<kind>/<name>.md`.

    Prompts are prose read by people as often as by the agent, so they
    live as Markdown files named after their seed row, not as escaped
    strings inside the JSON. A missing file is an error, never an empty
    prompt.
    """
    return (settings.SEEDS / "prompts" / kind / f"{name}.md").read_text()


def work_order(chosen: dict) -> str:
    """What the agent reads: the task type's contract, then the ask.

    `seeds/prompts/task_types/<task_type>.md` and
    `seeds/prompts/manifests/<name>.md`, joined; no routes, no case names.
    """
    kind = task_type(chosen["task_type"])
    ask = _prompt("manifests", chosen["name"])
    solve = sample(chosen["sample"]).get("solve", {})
    try:
        base = _prompt("task_types", kind["name"]).format(**solve)
    except KeyError as missing:
        raise ValueError(
            f"sample {chosen['sample']!r} has no solve {missing.args[0]!r}"
        ) from None
    return f"{base.rstrip()}\n\n{ask.rstrip()}\n"
