"""Inspect entry file: `inspect eval inspect_bench.py@slice_task`.

Inspect loads tasks from a *file* and finds them by parsing that file's AST
for `@task` decorators, so the two task definitions live here, at the
repository root, and nothing else does. The bench itself is `src/bench/`,
one module per concern: the sandbox compose, the seeds, the case player, and
one scorer per gate.

    inspect eval inspect_bench.py@topology_task -T sample=mamute \
        -T manifest=vote-flow --model mockllm/model
"""

import sys
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.solver import Generate, Solver, TaskState, solver

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.bench.scorers.parity import parity  # noqa: E402
from src.bench.scorers.topology import network_isolation  # noqa: E402
from src.bench.seeds import manifest as load_manifest  # noqa: E402
from src.bench.seeds import task_type, work_order  # noqa: E402
from src.bench.settings import SANDBOX  # noqa: E402


@solver
def submitted_tree() -> Solver:
    """The agent stage.

    The stack is the sandbox Inspect boots, so there is nothing to start
    here: this stands where the agent's run will go. For now it grades the
    tree as it stands, which is exactly what the no-op self-check wants.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        return state

    return solve


@task
def slice_task(sample: str, manifest: str) -> Task:
    """One slice: the work order, the stack, every case it names."""
    chosen = load_manifest(sample, manifest)
    kind = task_type(chosen["task_type"])
    cases = chosen["scope"]["cases"]
    return Task(
        # One sample per case: Inspect gives each its own sandbox, which is
        # what a golden captured on a pristine database requires.
        dataset=[
            Sample(
                input=work_order(chosen),
                target="decoupled",
                metadata={"case": case, "manifest": chosen["name"]},
            )
            for case in cases
        ],
        solver=[submitted_tree()],
        scorer=parity(
            sample,
            chosen["bindings"]["db"]["options"]["service"],
            chosen["bindings"]["db"]["options"]["database"],
        ),
        description=kind["description"],
        metadata={
            "task_type": kind["name"],
            "sample": sample,
            "manifest_version": chosen["version"],
        },
        sandbox=("docker", str(SANDBOX)),
    )


@task
def topology_task(sample: str, manifest: str) -> Task:
    """One gate on its own: it reads files, so it needs no stack."""
    chosen = load_manifest(sample, manifest)
    db_service = chosen["bindings"]["db"]["options"]["service"]
    return Task(
        dataset=[
            Sample(
                input=work_order(chosen),
                target="isolated",
                metadata={"sample": sample},
            )
        ],
        solver=[submitted_tree()],
        scorer=network_isolation(sample, db_service),
        description="The stack's declared topology, read statically.",
        metadata={"task_type": chosen["task_type"], "sample": sample},
    )
