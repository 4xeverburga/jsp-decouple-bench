"""Inspect entry points: `solve_task` and `score_task`; users run both via
`make task`.

Inspect loads tasks from a *file* and finds them by parsing that file's AST
for `@task` decorators, so the task definitions live here, at the repository
root, and nothing else does. The bench itself is `src/bench/`.

Every task is addressed by a **manifest id** — the unit of work, naming a
sample, a slice, a task type and the cases that slice is graded against. The
two task types differ only in their work order: `decouple_slice` names one
feature boundary, `oneshot_decoupling` names the whole app, and both list the
cases they are graded on, so one sample per case serves either.

    inspect eval inspect_bench.py@score_task -T manifest_id=14 \
        --model mockllm/model
"""

import sys
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.util import sandbox

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.bench import (  # noqa: E402
    samples,
    settings,
    solves,
)
from src.bench.compose import sandbox_compose  # noqa: E402
from src.bench.scorers.functional_parity import parity  # noqa: E402
from src.bench.scorers.topology import network_isolation  # noqa: E402
from src.bench.seeds import manifest as load_manifest  # noqa: E402
from src.bench.seeds import task_type  # noqa: E402


def _scorers(chosen: dict) -> list:
    options = chosen["bindings"]["db"]["options"]
    builders = {
        "functional_parity": lambda: parity(
            chosen["source"],
            options["service"],
            options["database"],
        ),
        "network_isolation": lambda: network_isolation(
            chosen["source"],
            options["service"],
        ),
    }
    return [builders[name]() for name in chosen["scorers"]]


@solver
def submitted_tree() -> Solver:
    """The agent stage when there is no agent.

    The stack is the sandbox Inspect boots, so there is nothing to start
    here: this stands where the agent's run goes, and grades the tree as it
    stands — which is exactly what the no-op self-check wants.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        return state

    return solve


@solver
def agent_command(command: str) -> Solver:
    """The agent stage: one command, in the sandbox, prompt on stdin.

    This is what the harness used to be, minus the harness: `sandbox().exec`
    runs it inside the container Inspect provisioned, so it has the checkout
    and nothing else — no docker socket, no supervisor home.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        result = await sandbox().exec(
            ["bash", "-lc", command],
            cwd=settings.checkout(),
            input=state.input_text,
        )
        state.metadata["command"] = command
        state.metadata["exit_code"] = result.returncode
        state.metadata["stdout"] = (result.stdout or "")[-4000:]
        state.metadata["stderr"] = (result.stderr or "")[-4000:]
        state.output.completion = result.stdout or ""
        return state

    return solve


async def capture_solution(state: TaskState) -> None:
    """Keep the tree the agent left, so a score can be re-run without it."""
    solves.capture(
        state.metadata["run"],
        Path(settings.checkout()),
        {
            "command": state.metadata["command"],
            "exit_code": state.metadata["exit_code"],
            "manifest_id": state.metadata["manifest_id"],
        },
    )


@task
def solve_task(manifest_id: int, run: str, agent: str) -> Task:
    """Let an agent work on one manifest; keep what it leaves behind."""
    chosen = load_manifest(manifest_id)
    return Task(
        dataset=samples.for_solving(manifest_id, run),
        solver=[agent_command(agent)],
        cleanup=capture_solution,
        description=task_type(chosen["task_type"])["description"],
        metadata={
            "manifest": chosen["name"],
            "task_type": chosen["task_type"],
            "sample": chosen["source"],
            "version": chosen["version"],
        },
        sandbox=("docker", str(settings.sandbox())),
    )


@task
def score_task(manifest_id: int) -> Task:
    """Grade a manifest: one sample per case, each on a fresh stack."""
    chosen = load_manifest(manifest_id)
    kind = task_type(chosen["task_type"])
    return Task(
        dataset=samples.for_scoring(manifest_id),
        solver=[submitted_tree()],
        scorer=_scorers(chosen),
        description=kind["description"],
        metadata={
            "manifest": chosen["name"],
            "task_type": kind["name"],
            "sample": chosen["source"],
            "version": chosen["version"],
        },
        sandbox=(
            "docker",
            str(sandbox_compose(chosen["source"], settings.checkout())),
        ),
    )
