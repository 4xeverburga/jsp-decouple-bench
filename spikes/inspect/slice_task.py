"""Can a bench slice be an Inspect Task? Answer by building one.

Nothing here is invented: the work order is composed from
`seeds/task_types.json` + `seeds/manifests.json` exactly as
`src/tasks/base.py` composes it, the manifest's `scope.cases` become the
scorers, and the manifest's bindings become the Task's sandbox and limits.

A stub agent stands in for the real one — it reports a partial result on
purpose, so the log shows per-case verdicts and what each reduction makes
of them. It never calls the model, so this runs in seconds:

    inspect eval spikes/inspect/slice_task.py -T sample=mamute \
        -T manifest=vote-flow --model mockllm/model

What this probe is *not*: an implementation. It carries no sandbox, does
not provision the pin, and grades a dictated verdict instead of a
checkout. It exists to settle which parts of our model land on Task
fields and which do not.
"""

import json
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    Metric,
    SampleScore,
    Score,
    Value,
    metric,
    scorer,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver

ROOT = Path(__file__).resolve().parents[2]
SEEDS = ROOT / "seeds"

# The stub claims this one case and fails the rest, so a mixed verdict is
# visible in the log rather than a tidy 1.0 or 0.0.
STUB_PASSES = "upvote-increments-count"


def _seed(name: str) -> list[dict]:
    return json.loads((SEEDS / name).read_text())


def _task_type(kind: str) -> dict:
    for candidate in _seed("task_types.json"):
        if candidate["name"] == kind:
            return candidate
    raise KeyError(kind)


def _manifest(sample: str, name: str) -> dict:
    for candidate in _seed("manifests.json"):
        if candidate["sample"] == sample and candidate["name"] == name:
            return candidate
    raise KeyError(f"{sample}/{name}")


def work_order(manifest: dict) -> str:
    """The two data fields the agent reads, verbatim — no scope, no cases."""
    kind = _task_type(manifest["task_type"])
    return (
        f"{kind['base_prompt'].rstrip()}\n\n"
        f"{manifest['prompt'].rstrip()}\n"
    )


@solver
def stub_agent() -> Solver:
    """Stand-in for the agent: reports what it changed, changes nothing."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        state.metadata["changed_files"] = [
            "src/main/webapp/assets/js/up-down-vote.js"
        ]
        state.metadata["backend_touched"] = False
        return state

    return solve


@scorer(metrics=[])
def behaviour_case(case: str) -> scorer:
    """One graded behaviour, the way one functional-parity case is graded."""

    async def score(state: TaskState, target: Value) -> Score:
        # A real implementation replays the flow against the running stack
        # and compares the captured deltas with the frozen golden. The stub
        # decides from its own claim so the shape is what gets exercised.
        passed = case.endswith(STUB_PASSES)
        return Score(
            value=CORRECT if passed else INCORRECT,
            answer=", ".join(state.metadata["changed_files"]),
            explanation=(
                f"case={case} backend_touched="
                f"{state.metadata['backend_touched']}"
            ),
            metadata={"case": case},
        )

    return score


@metric
def all_must_pass() -> Metric:
    """Our gate rule: a run passes only if every case passes.

    Inspect's own metrics average, which would report 0.5 for a run that
    decoupled nothing — the exact failure this bench exists to catch.

    Note this can only be a *task-level* rule if the cases are folded into
    one scorer: Inspect computes a metric per scorer, so N scorers yield N
    verdicts and never one AND over them. `all_cases` below does the fold.
    """

    def compute(scores: list[SampleScore]) -> Value:
        values = [float(score.score.value) for score in scores]
        return min(values) if values else 0.0

    return compute


@scorer(metrics=[all_must_pass()])
def all_cases(cases: list[str]) -> scorer:
    """Every graded case, folded into the single verdict the gate reports."""

    async def score(state: TaskState, target: Value) -> Score:
        verdicts = {
            case: case.endswith(STUB_PASSES) for case in cases
        }
        passed = all(verdicts.values())
        return Score(
            value=CORRECT if passed else INCORRECT,
            answer=", ".join(state.metadata["changed_files"]),
            explanation="; ".join(
                f"{case}={'pass' if ok else 'fail'}"
                for case, ok in verdicts.items()
            ),
            metadata={
                "cases": {
                    case: "pass" if ok else "fail"
                    for case, ok in verdicts.items()
                },
                "backend_touched": state.metadata["backend_touched"],
            },
        )

    return score


@task
def slice_task_strict(sample: str, manifest: str) -> Task:
    """The same slice, graded the way our gate reports it."""
    chosen = _manifest(sample, manifest)
    cases = chosen["scope"]["cases"]
    kind = _task_type(chosen["task_type"])
    return Task(
        dataset=[
            Sample(
                input=work_order(chosen),
                target="decoupled",
                metadata={"cases": cases},
            )
        ],
        solver=[stub_agent()],
        scorer=all_cases(cases),
        metrics=[all_must_pass()],
        description=kind["description"],
        metadata={
            "task_type": kind["name"],
            "sample": sample,
            "manifest_version": chosen["version"],
        },
    )


@task
def slice_task(sample: str, manifest: str) -> Task:
    chosen = _manifest(sample, manifest)
    cases = chosen["scope"]["cases"]
    kind = _task_type(chosen["task_type"])
    return Task(
        dataset=[
            Sample(
                input=work_order(chosen),
                target="decoupled",
                metadata={
                    "sample": sample,
                    "manifest": chosen["name"],
                    "manifest_version": chosen["version"],
                    "cases": cases,
                    # Recorded here only because a probe cannot grade; a real
                    # task must not carry the routes it is judged on into
                    # anything the agent reads.
                    "routes": chosen["scope"]["routes"],
                },
            )
        ],
        solver=[stub_agent()],
        scorer=[behaviour_case(case) for case in cases],
        metrics=[all_must_pass()],
        description=kind["description"],
        metadata={
            "task_type": kind["name"],
            "sample": sample,
            "manifest_version": chosen["version"],
        },
        # The manifest's bindings map onto Task options directly.
        sandbox=None,
    )
