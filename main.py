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
        -T opencode_model=opencode-go/deepseek-v4.1-flash \
        -T model_target=mockllm/model \
        --model mockllm/model
"""

import os
import sys
import uuid
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.model import Model, get_model
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_swe import opencode

sys.path.insert(0, str(Path(__file__).resolve().parent))

import settings  # noqa: E402
from src.bench import samples, solves  # noqa: E402
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
    solves.capture(
        state.metadata["run"],
        Path(settings.checkout()),
        {
            "agent": "inspect_swe.opencode",
            "opencode_model": state.metadata["opencode_model"],
            # The CLI's name is only the wire format; this is what answered.
            "model": state.metadata["model_target"],
            "manifest_id": state.metadata["manifest_id"],
        },
    )


# OpenCode 2.x starts a managed background service before it answers, and in a
# bare sandbox that service never comes up (`Unexpected server error`, or a
# hang on its fixed port). 1.x talks to the bridge directly. The pinned
# version lives in `.env` (`OPENCODE_VERSION`); change it only to one that
# has been shown to work in the sandbox.


def _aliases(
    opencode_model: str, model_target: str
) -> dict[str, Model] | None:
    """Route the name OpenCode asks for to the model that answers.

    The bridge declines any model name it does not know (`Add ... to
    model_aliases`), and the agent's model string is only the wire format:
    the answer comes from the eval's model. Alias both spellings so the
    shape of the string the CLI sends cannot matter.

    The alias is a Model instance, not a name: resolving a bare string builds
    a model without the args the eval was given, and a gateway that needs a
    routing header rejects that one.
    """
    if not model_target:
        return None
    session = os.environ.get("OPENCODE_SESSION_ID")
    if session is None:
        session = uuid.uuid4().hex
    model = get_model(
        model_target,
        default_headers={"x-opencode-session": session},
    )
    bare = opencode_model.rsplit("/", 1)[-1]
    return {bare: model, opencode_model: model}


def _manifest_task(
    manifest_id: int,
    phase: str,
    run: str,
    opencode_model: str,
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
                manifest_id, run, opencode_model, model_target
            ),
            solver=opencode(
                cwd=settings.checkout(),
                opencode_model=opencode_model,
                version=settings.OPENCODE_VERSION,
                model_aliases=_aliases(opencode_model, model_target),
                # The bridge answers whatever credential the CLI presents;
                # the provider still wants one to consider itself ready.
                env={"OPENCODE_API_KEY": "sk-none"},
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
    opencode_model: str,
    model_target: str,
) -> Task:
    """Run the solve or score phase for a decouple_slice manifest."""
    return _manifest_task(
        manifest_id,
        phase,
        run,
        opencode_model,
        "decouple_slice",
        model_target,
    )


@task
def oneshot_decoupling(
    manifest_id: int,
    phase: str,
    run: str,
    opencode_model: str,
    model_target: str,
) -> Task:
    """Run the solve or score phase for an oneshot_decoupling manifest."""
    return _manifest_task(
        manifest_id,
        phase,
        run,
        opencode_model,
        "oneshot_decoupling",
        model_target,
    )


@task
def dummy_file(
    manifest_id: int,
    phase: str,
    run: str,
    opencode_model: str,
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
        opencode_model,
        "dummy_file",
        model_target,
    )


if __name__ == "__main__":
    from src.bench.cli import main

    main(sys.argv[1:])
