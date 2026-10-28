"""functional_parity as a scorer: one sample, one case.

Each case is its own Sample, so Inspect provisions a fresh stack for it —
which is what the goldens assume. They were captured against a pristine
database, and a case that ran after another would see its rows.

Two things are compared: the browser artifacts, and the database delta the
flow caused. The second is what makes the gate falsifiable — a submission
that moves the vote count in the DOM without writing the vote row passes the
first and fails the second.

The manifest's verdict is the metric, not this score: `all_must_pass`
reduces across samples, so a manifest passes only if every case does.
"""

import asyncio

from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, scorer
from inspect_ai.solver import TaskState

from .. import db, settings
from ..cases import golden, play
from ..delta import canonical, delta_table
from .metrics import all_must_pass


def _db_differences(
    slug: str, case: str, before: dict, after: dict
) -> list[str]:
    tables = golden(slug, case)["db"]["tables"]
    differing: list[str] = []
    for table, spec in tables.items():
        actual = delta_table(
            before[table],
            after[table],
            spec["key_columns"],
            spec["ignore_columns"],
        )
        if canonical(actual) != canonical(spec):
            differing.append(f"db:{table}")
    return differing


def _keep(
    staged: str | None, slug: str, case: str, failed: bool
) -> str | None:
    """Promote a staged shot when the case failed; drop it when it passed.

    The path is per case, so only the latest failure kept — but a pass never
    erases a failure's evidence, which is the property that matters.
    """
    if not staged:
        return None
    source = settings.ROOT / staged
    if not failed:
        source.unlink(missing_ok=True)
        return None
    target = settings.EVIDENCE / slug / f"{case}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    source.replace(target)
    return str(target.relative_to(settings.ROOT))


@scorer(metrics=[all_must_pass()])
def parity(slug: str, db_service: str, database: str) -> scorer:
    """Grade the case this sample names, artifacts and rows both."""

    async def score(state: TaskState, target: Target) -> Score:
        case = state.metadata["case"]
        tables = list(golden(slug, case)["db"]["tables"])
        before = await db.snapshot(db_service, database, tables)
        artifacts = await asyncio.to_thread(play, slug, case)
        after = await db.snapshot(db_service, database, tables)

        browser = artifacts["differing"]
        rows = _db_differences(slug, case, before, after)
        differing = browser + rows
        shot = _keep(artifacts["screenshot"], slug, case, bool(differing))
        return Score(
            value=INCORRECT if differing else CORRECT,
            answer=case,
            explanation=(
                f"{case}=pass"
                if not differing
                else f"{case}=differs:{','.join(differing)}"
            ),
            # The screenshot is the evidence a reader needs: without it a
            # failure is a list of keys, and no one can say what it looked
            # like.
            metadata={
                "case": case,
                "artifacts": browser,
                "db": rows,
                "screenshot": shot,
            },
        )

    return score
