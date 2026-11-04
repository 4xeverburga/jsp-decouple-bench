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

import asyncio
from pathlib import Path
from uuid import uuid4

from inspect_ai.solver import Generate, Solver, TaskState, solver

import settings

from .scorers.functional_parity import db
from .scorers.functional_parity.cases import FlowAssertionError, golden, play
from .scorers.functional_parity.delta import delta_table
from .scorers.observation import STORE_KEY
from .stack import running


async def keep_trace(stack, slug: str, case: str) -> Path | None:
    """Copy the case's spans out: the volume dies with the stack.

    Their only other copy is inside the collector's volume, which
    `down -v` deletes whatever the verdict was. Wait out the export batch
    first, then take the file. None when there is no file: whether that is
    fatal is the reader's call — parity grades behaviour without it,
    `trace_similarity` cannot grade at all.
    """
    target = settings.TRACES / slug / f"{case}-{uuid4().hex[:8]}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.sleep(settings.TRACE_FLUSH_WAIT_S)
    copied = await asyncio.to_thread(
        stack.copy_out,
        settings.STACK_TRACES_SERVICE,
        settings.STACK_TRACES_FILE,
        target,
    )
    return target if copied else None


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
        failure = None
        artifacts = None
        async with running(slug) as stack:
            before = await db.snapshot(stack, target, list(specs))
            try:
                artifacts = await asyncio.to_thread(
                    play, slug, case, stack.base_url
                )
            except FlowAssertionError as error:
                failure = {
                    "reason": error.reason,
                    "screenshot": error.screenshot,
                }
            after = await db.snapshot(stack, target, list(specs))
            trace = await keep_trace(stack, slug, case)
        # The rows are observed either way: when the flow itself failed,
        # the delta is often the better evidence (the page looked right,
        # nothing was written).
        state.store.set(
            STORE_KEY,
            {
                "case": case,
                "failure": failure,
                "artifacts": artifacts,
                "deltas": {
                    table: delta_table(
                        before[table],
                        after[table],
                        spec["key_columns"],
                        spec["ignore_columns"],
                    )
                    for table, spec in specs.items()
                },
                "trace": (
                    None
                    if trace is None
                    else str(trace.relative_to(settings.ROOT))
                ),
            },
        )
        return state

    return solve
