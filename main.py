"""Inspect task types: `decouple_slice` and `oneshot_decoupling`.

`python main.py task` runs the solve phase of one manifest;
`python main.py score` runs the score phase on the tree it kept.

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
        -T profile=judge-claude-opus-5.5-high --model mockllm/model

`profile` is the profile of the phase that runs, so neither phase is handed
a value it does not read. In a solve it names a `solve_profiles` entry of
`tasks-config.yaml`: who solves, and the model that answers it. In a score
it names a `score_profiles` entry: the model that judges the spans. A score
labels itself with the solve profile from the run's own record, so a
re-score of last week's tree carries the profile that produced it.
"""

import base64
import os
import sys
import uuid
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.model import GenerateConfig, Model, get_model
from inspect_ai.solver import TaskState
from inspect_ai.util import sandbox as host_sandbox

sys.path.insert(0, str(Path(__file__).resolve().parent))

import settings  # noqa: E402
from src import agents  # noqa: E402
from src.bench import samples, solves  # noqa: E402
from src.bench.compose import solve_compose  # noqa: E402
from src.bench.replay import replayed_case  # noqa: E402
from src.bench.scorers import parity, trace_similarity  # noqa: E402
from src.bench.seeds import manifest as load_manifest  # noqa: E402
from src.bench.seeds import task_type  # noqa: E402


def _scorers(chosen: dict, score_profile: str) -> list:
    builders = {
        "functional_parity": lambda: parity(chosen["sample"]),
        "trace_similarity": lambda: trace_similarity(
            chosen["sample"],
            score_profile,
            settings.score_profile(score_profile),
        ),
    }
    return [builders[name]() for name in chosen["scorers"]]


async def capture_solution(state: TaskState) -> None:
    """Keep the tree the agent left, so a score can be re-run without it."""
    run = state.metadata["run"]
    resolved = state.metadata["resolved"]
    agent = resolved["agent"]
    solves.capture(
        run,
        Path(settings.checkout()),
        {
            # The name a run was asked for, and what it meant at the time:
            # a profile can be edited after the run, its record cannot.
            "profile": state.metadata["profile"],
            **resolved,
            # The CLI's name is only the wire format; this is what answered.
            "model": resolved["answer_model"],
            "manifest_id": state.metadata["manifest_id"],
            # A manifest's prompt is versioned, so a tree from one version
            # cannot be compared with another: say which one produced it.
            "manifest_version": state.metadata["manifest_version"],
        },
    )
    await _keep_agent(run, agent)


async def _keep_agent(run: str, agent: str) -> None:
    """Copy a CLI session record out before the sandbox is removed.

    The library hands the agent's stdout back in memory and drops it after
    the run, so CLI tool calls are kept from the agent's state directory.
    Native ReAct has no separate state directory; its tool calls are in the
    Inspect eval log.
    """
    state = agents.state(agent)
    if state is None:
        return
    try:
        box = host_sandbox()
        done = await box.exec(
            [
                "sh",
                "-c",
                f"cd {state} && tar -cf - . | base64 -w0",
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


def _answer_model(resolved: dict) -> Model:
    """The model that answers the agent's calls, whatever they were named.

    A Model instance, not a name: resolving a bare string builds a model
    without the args the eval was given, and a gateway that needs a routing
    header rejects that one. Because it is built here it is not the eval's
    active model, and Inspect merges the eval's `--reasoning-effort` and
    `-M` only into that one — so the profile's effort and arguments are
    set on this model directly, or they would never reach a request.
    """
    session = os.environ.get("OPENCODE_SESSION_ID")
    if session is None:
        session = uuid.uuid4().hex
    return get_model(
        resolved["answer_model"],
        config=GenerateConfig(reasoning_effort=resolved["reasoning_effort"]),
        default_headers={SESSION_HEADER: session},
        **resolved["model_args"],
    )


def _manifest_task(
    manifest_id: int,
    phase: str,
    run: str,
    profile: str,
    expected_type: str,
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
        "sample": chosen["sample"],
        "version": chosen["version"],
    }
    # Two budgets, because they bound different things. A solve is the
    # agent's own working time; a score is stack builds and case replays,
    # which has nothing to do with how long an agent may think. Both come
    # from the manifest — the only place a run's length is decided — and
    # neither has a default here (AGENTS.md rule 10).

    if phase == "solve":
        resolved = settings.solve_profile(profile)
        return Task(
            dataset=samples.for_solving(manifest_id, run, profile, resolved),
            solver=agents.solver_for(
                resolved["agent"],
                _answer_model(resolved),
                resolved["agent_model"],
                resolved["agent_version"],
                settings.SOLVE_ROOT,
            ),
            cleanup=capture_solution,
            description=kind["description"],
            metadata=metadata,
            time_limit=chosen["solve_time_limit_minutes"] * 60,
            sandbox=("docker", str(solve_compose(chosen["sample"]))),
        )

    if phase == "score":
        # Which solve produced the tree, from its record: the label every
        # verdict in this log is read against.
        metadata["solve_profile"] = solves.read(run)["profile"]
        metadata["run"] = run
        return Task(
            dataset=samples.for_scoring(manifest_id),
            # The case is played once, here; every scorer judges that run.
            solver=[
                replayed_case(
                    chosen["sample"], chosen["bindings"]["db"]["options"]
                )
            ],
            scorer=_scorers(chosen, profile),
            description=kind["description"],
            metadata=metadata,
            time_limit=chosen["score_time_limit_minutes"] * 60,
        )

    raise ValueError(f"unknown task phase: {phase}")


@task
def decouple_slice(
    manifest_id: int,
    phase: str,
    run: str,
    profile: str,
) -> Task:
    """Run the solve or score phase for a decouple_slice manifest."""
    return _manifest_task(
        manifest_id,
        phase,
        run,
        profile,
        "decouple_slice",
    )


@task
def oneshot_decoupling(
    manifest_id: int,
    phase: str,
    run: str,
    profile: str,
) -> Task:
    """Run the solve or score phase for an oneshot_decoupling manifest."""
    return _manifest_task(
        manifest_id,
        phase,
        run,
        profile,
        "oneshot_decoupling",
    )


@task
def dummy_file(
    manifest_id: int,
    phase: str,
    run: str,
    profile: str,
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
        profile,
        "dummy_file",
    )


@task
def agent_probe(
    manifest_id: int,
    phase: str,
    run: str,
    profile: str,
) -> Task:
    """Probe only: read a few files, write one, stop. No app work.

    `dummy_file` proves an agent acts at all; it cannot prove an agent ever
    stops researching, because it has no read phase. Here the read phase
    comes first, so the run's `diff.patch` says whether the agent turned
    reading into an edit. Parity is green by construction, as with
    `dummy_file`, and says nothing about the agent.
    """
    return _manifest_task(
        manifest_id,
        phase,
        run,
        profile,
        "agent_probe",
    )


if __name__ == "__main__":
    from src.bench.cli import main

    main(sys.argv[1:])
