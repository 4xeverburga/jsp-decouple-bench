"""Replaying one case on the tree under test: observe once, judge many.

A case's stack is minutes to build and its flow is the expensive part of a
score, and every scorer needs the same run of it: `functional_parity` the
page and the rows it left, `trace_similarity` the spans that served it.
Playing the flow once per scorer would also mean grading two different runs
of the app. So the score phase's solver plays it, here, and leaves what it
saw in the sample's store; the scorers only compare.

    state.store["replay"] = {
        "case": ...,
        "failure": None | {"reason": ..., "screenshot": ...},
        "artifacts": None | {"differing": [...], "screenshot": ...},
        "deltas": {table: delta},      # the tables the golden names
        "trace": "out/traces/<slug>/<case>-<hash>.jsonl" | None,
    }

What is stored is an observation, not a verdict: the deltas are the rows
the flow changed, keyed and filtered by the golden's own table specs, so
the scorer can compare them; whether they match is the scorer's call.
"""

from inspect_ai.solver import Generate, Solver, TaskState, solver

import settings
from src.core.cases import db
from src.core.cases.cases import compare, golden
from src.core.observe import observe

from .scorers.observation import STORE_KEY


@solver
def replayed_case(slug: str, options: dict) -> Solver:
    """Play the sample's case once on the tree under test, on its own stack.

    `options` is the manifest's `bindings.db.options`, as data, so the
    run's log records which database the rows were read from.
    """
    target = db.Target.from_options(options)

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        case = state.metadata["case"]
        specs = golden(slug, case)["db"]["tables"]
        seen = await observe(slug, case, specs, target)
        state.store.set(
            STORE_KEY,
            {
                "case": case,
                "failure": seen.failure,
                "artifacts": (
                    None
                    if seen.artifacts is None
                    else compare(slug, case, seen.artifacts, seen.screenshot)
                ),
                "deltas": seen.deltas,
                "trace": (
                    None
                    if seen.trace is None
                    else str(seen.trace.relative_to(settings.ROOT))
                ),
            },
        )
        return state

    return solve
