"""The seeds: what a slice is, and the work order a run receives."""

import json

from .settings import SEEDS


def _seed(name: str) -> list[dict]:
    return json.loads((SEEDS / name).read_text())


def task_type(kind: str) -> dict:
    for candidate in _seed("task_types.json"):
        if candidate["name"] == kind:
            return candidate
    raise KeyError(kind)


def manifest(sample: str, name: str) -> dict:
    for candidate in _seed("manifests.json"):
        if candidate["sample"] == sample and candidate["name"] == name:
            return candidate
    raise KeyError(f"{sample}/{name}")


def pin(sample: str) -> str:
    for row in _seed("samples.json"):
        if row["slug"] == sample:
            return row["commit_sha"]
    raise KeyError(sample)


def work_order(chosen: dict) -> str:
    """The two data fields the agent reads — no routes, no case names."""
    kind = task_type(chosen["task_type"])
    return (
        f"{kind['base_prompt'].rstrip()}\n\n"
        f"{chosen['prompt'].rstrip()}\n"
    )
