"""functional_parity as a scorer: one sample, one case.

Each case is its own Sample and gets its own stack, started and removed by
the scorer — which is what the goldens assume. They were captured against a
pristine database, and a case that ran after another would see its rows.

Two things are compared: the browser artifacts, and the database delta the
flow caused. The second is what makes the gate falsifiable — a submission
that moves the vote count in the DOM without writing the vote row passes the
first and fails the second.

The manifest's verdict is the metric, not this score: `all_must_pass`
reduces across samples, so a manifest passes only if every case does.
"""

import asyncio
from uuid import uuid4

from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, scorer
from inspect_ai.solver import TaskState

import settings

from ...stack import running
from ..metrics import all_must_pass
from . import db
from .cases import golden, play
from .delta import canonical, delta_table, summary


def _db_differences(
    slug: str, case: str, before: dict, after: dict
) -> tuple[list[str], dict]:
    """The tables that differ, and what they actually changed.

    The delta is returned, not just its name: "db:Vote differs" is a label,
    while "Vote inserted 0!=1" is the bug.
    """
    tables = golden(slug, case)["db"]["tables"]
    differing: list[str] = []
    detail: dict[str, dict] = {}
    for table, spec in tables.items():
        actual = delta_table(
            before[table],
            after[table],
            spec["key_columns"],
            spec["ignore_columns"],
        )
        if canonical(actual) != canonical(spec):
            differing.append(f"db:{table}")
            detail[table] = actual
    return differing, detail


def _screenshot(staged: str | None, failed: bool) -> str | None:
    """Keep a failure's picture; a pass drops only its own.

    The staged name carries a random suffix, so concurrent runs of the same
    case cannot land on one path.
    """
    if not staged:
        return None
    if failed:
        return staged
    (settings.ROOT / staged).unlink(missing_ok=True)
    return None


async def _trace(stack, slug: str, case: str) -> str | None:
    """Keep the case's spans: the volume dies with the stack.

    Their only other copy is inside the collector's volume, which
    `down -v` deletes whatever the verdict was. Wait out the export batch
    first, then take the file. Best effort like the screenshot: a case
    that failed on its behaviour must report that, not a second error.
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
    if not copied:
        return None
    return str(target.relative_to(settings.ROOT))


@scorer(metrics=[all_must_pass()])
def parity(slug: str, options: dict) -> scorer:
    """Grade the case this sample names, artifacts and rows both.

    `options` is the manifest's `bindings.db.options`: which service holds
    the database, which database, whose user, and which SQL dialect. It is
    passed through as data rather than as a live object so the run's log
    records what was graded against.
    """
    target = db.Target.from_options(options)

    async def score(state: TaskState, target_state: Target) -> Score:
        case = state.metadata["case"]
        tables = list(golden(slug, case)["db"]["tables"])
        async with running(slug) as stack:
            before = await db.snapshot(stack, target, tables)
            artifacts = await asyncio.to_thread(play, slug, case)
            after = await db.snapshot(stack, target, tables)
            trace = await _trace(stack, slug, case)

        browser = artifacts["differing"]
        rows, detail = _db_differences(slug, case, before, after)
        differing = browser + rows
        shot = _screenshot(artifacts["screenshot"], bool(differing))
        expected = {
            table: golden(slug, case)["db"]["tables"][table]
            for table in detail
        }
        return Score(
            value=INCORRECT if differing else CORRECT,
            answer=case,
            explanation=(
                f"{case}=pass"
                if not differing
                else f"{case}=differs:{','.join(differing)} "
                f"[{summary({'tables': detail}, {'tables': expected})}]"
            ),
            metadata={
                "case": case,
                "artifacts": browser,
                "db": rows,
                "db_delta": detail,
                "screenshot": shot,
                "trace": trace,
            },
        )

    return score
