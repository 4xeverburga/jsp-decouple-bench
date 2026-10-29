"""Inspect task types: `decouple_slice` and `oneshot_decoupling`.

`python main.py task` runs the solve and score phases of one manifest.

Inspect loads tasks from a *file* and finds them by parsing that file's AST
for `@task` decorators, so the task definitions live here, at the repository
root, and nothing else does. The bench itself is `src/bench/`, and the verbs
that drive these tasks are `src/bench/cli.py`.

Every task is addressed by a **manifest id** — the unit of work, naming a
sample, a slice, a task type and the cases that slice is graded against. The
two task types differ only in their work order: `decouple_slice` names one
feature boundary, `oneshot_decoupling` names the whole app, and both list the
cases they are graded on, so one sample per case serves either.

    inspect eval main.py@oneshot_decoupling \
        -T manifest_id=14 -T phase=score -T run=<id> \
        -T agent=opencode -T agent_model=opencode-go/deepseek-v4.1-flash \
        -T agent_version=1.19.5 -T model_target=mockllm/model \
        --model mockllm/model
"""

import base64
import os
import sys
import uuid
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.model import Model, get_model
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.util import sandbox as host_sandbox

sys.path.insert(0, str(Path(__file__).resolve().parent))

import settings  # noqa: E402
from src.bench import agents, samples, solves  # noqa: E402
from src.bench.compose import solve_compose  # noqa: E402
from src.bench.scorers.functional_parity import parity  # noqa: E402
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
    }
    return [builders[name]() for name in chosen["scorers"]]


@solver
def submitted_tree() -> Solver:
    """The agent stage when there is no agent.

    The scorer starts the stack itself (src/bench/stack.py), so there is
    nothing to start here: this stands where the agent's run goes, and
    grades the tree as it stands — which is exactly what the no-op
    self-check wants.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        return state

    return solve


async def capture_solution(state: TaskState) -> None:
    """Keep the tree the agent left, so a score can be re-run without it."""
    run = state.metadata["run"]
    agent = state.metadata["agent"]
    solves.capture(
        run,
        Path(settings.checkout()),
        {
            "agent": agent,
            "agent_model": state.metadata["agent_model"],
            "agent_version": state.metadata["agent_version"],
            # The CLI's name is only the wire format; this is what answered.
            "model": state.metadata["model_target"],
            "manifest_id": state.metadata["manifest_id"],
        },
    )
    await _keep_agent(run, agent)


async def _keep_agent(run: str, agent: str) -> None:
    """Copy the CLI's session record out before the sandbox is removed.

    The library hands the agent's stdout back in memory and drops it after
    the run, and the eval log holds the work order and the scores but not
    the tool calls in between, so this is the only way a finished run can
    be read afterwards. Where that record lives is the agent's own
    business: `agents.state(name)` says.
    """
    try:
        box = host_sandbox()
        done = await box.exec(
            [
                "sh",
                "-c",
                f"cd {agents.state(agent)} && tar -cf - . | base64 -w0",
            ]
        )
    except Exception:  # no sandbox left, or nothing to copy
        return
    if done.returncode != 0 or not done.stdout.strip():
        return
    solves.keep_agent(run, base64.b64decode(done.stdout))


# The answering provider's gateway rejects a request that carries no session
# header, and the id is only there so one run's calls group together. A
# provider that does not know the header ignores it.
SESSION_HEADER = "x-opencode-session"


def _answer_model(model_target: str) -> Model:
    """The model that answers the agent's calls, whatever they were named.

    A Model instance, not a name: resolving a bare string builds a model
    without the args the eval was given, and a gateway that needs a routing
    header rejects that one.
    """
    session = os.environ.get("OPENCODE_SESSION_ID")
    if session is None:
        session = uuid.uuid4().hex
    return get_model(
        model_target,
        default_headers={SESSION_HEADER: session},
    )


def _manifest_task(
    manifest_id: int,
    phase: str,
    run: str,
    agent: str,
    agent_model: str,
    agent_version: str,
    expected_type: str,
    model_target: str,
) -> Task:
    chosen = load_manifest(manifest_id)
    if chosen["task_type"] != expected_type:
        raise ValueError(
            f"manifest {manifest_id} is {chosen['task_type']}, "
            f"not {expected_type}"
        )
    kind = task_type(chosen["task_type"])
    metadata = {
        "manifest": chosen["name"],
        "task_type": chosen["task_type"],
        "sample": chosen["source"],
        "version": chosen["version"],
    }

    if phase == "solve":
        if run is None:
            raise ValueError("solve phase requires run")
        return Task(
            dataset=samples.for_solving(
                manifest_id,
                run,
                agent,
                agent_model,
                agent_version,
                model_target,
            ),
            solver=agents.solver_for(
                agent,
                _answer_model(model_target),
                agent_model,
                agent_version,
                settings.SOLVE_ROOT,
            ),
            cleanup=capture_solution,
            description=kind["description"],
            metadata=metadata,
            sandbox=("docker", str(solve_compose(chosen["source"]))),
        )

    if phase == "score":
        return Task(
            dataset=samples.for_scoring(manifest_id),
            solver=[submitted_tree()],
            scorer=_scorers(chosen),
            description=kind["description"],
            metadata=metadata,
        )

    raise ValueError(f"unknown task phase: {phase}")


@task
def decouple_slice(
    manifest_id: int,
    phase: str,
    run: str,
    agent: str,
    agent_model: str,
    agent_version: str,
    model_target: str,
) -> Task:
    """Run the solve or score phase for a decouple_slice manifest."""
    return _manifest_task(
        manifest_id,
        phase,
        run,
        agent,
        agent_model,
        agent_version,
        "decouple_slice",
        model_target,
    )


@task
def oneshot_decoupling(
    manifest_id: int,
    phase: str,
    run: str,
    agent: str,
    agent_model: str,
    agent_version: str,
    model_target: str,
) -> Task:
    """Run the solve or score phase for an oneshot_decoupling manifest."""
    return _manifest_task(
        manifest_id,
        phase,
        run,
        agent,
        agent_model,
        agent_version,
        "oneshot_decoupling",
        model_target,
    )


@task
def dummy_file(
    manifest_id: int,
    phase: str,
    run: str,
    agent: str,
    agent_model: str,
    agent_version: str,
    model_target: str,
) -> Task:
    """Smoke test only: one new file, no app work.

    The tree comes back with exactly one added file and nothing else
    changed, so `functional_parity` — which only observes the running app —
    is green by construction. The signal is the run's `diff.patch`: it is
    the only place that says whether the agent acted at all. A green parity
    here says the pipeline works, not that an agent can modernize anything.
    """
    return _manifest_task(
        manifest_id,
        phase,
        run,
        agent,
        agent_model,
        agent_version,
        "dummy_file",
        model_target,
    )


if __name__ == "__main__":
    from src.bench.cli import main

    main(sys.argv[1:])
