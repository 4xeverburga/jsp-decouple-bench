"""functional_parity as a scorer: one sample, one case.

Each case is its own Sample and gets its own stack, because the goldens
were captured against a pristine database and a case that ran after another
would see its rows. The score phase's solver (`src/bench/replay.py`) starts
that stack, plays the flow once and leaves what it saw; this only compares.

Two things are compared: the browser artifacts, and the database delta the
flow caused. The second is what makes the gate falsifiable — a submission
that moves the vote count in the DOM without writing the vote row passes the
first and fails the second.

The manifest's verdict is the metric, not this score: `all_must_pass`
reduces across samples, so a manifest passes only if every case does.
"""

from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, scorer
from inspect_ai.solver import TaskState

import settings

from ..metrics import all_must_pass
from ..observation import observation
from .cases import golden
from .delta import canonical, summary


def _db_differences(
    slug: str, case: str, deltas: dict
) -> tuple[list[str], dict]:
    """The tables that differ, and what they actually changed.

    The delta is returned, not just its name: "db:Vote differs" is a label,
    while "Vote inserted 0!=1" is the bug.
    """
    tables = golden(slug, case)["db"]["tables"]
    differing: list[str] = []
    detail: dict[str, dict] = {}
    for table, spec in tables.items():
        actual = deltas[table]
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


@scorer(metrics=[all_must_pass()])
def parity(slug: str) -> scorer:
    """Grade the case this sample names, artifacts and rows both."""

    async def score(state: TaskState, target_state: Target) -> Score:
        seen = observation(state)
        case = seen["case"]
        trace = seen["trace"]
        failure = seen["failure"]
        rows, detail = _db_differences(slug, case, seen["deltas"])
        expected = {
            table: golden(slug, case)["db"]["tables"][table]
            for table in detail
        }
        if failure is not None:
            shot = _screenshot(failure["screenshot"], True)
            return Score(
                value=INCORRECT,
                answer=case,
                explanation=(
                    f"{case}=failed:{failure['reason']} "
                    f"[{summary({'tables': detail}, {'tables': expected})}]"
                ),
                metadata={
                    "case": case,
                    "artifacts": [],
                    "db": rows,
                    "db_delta": detail,
                    "screenshot": shot,
                    "trace": trace,
                },
            )

        artifacts = seen["artifacts"]
        browser = artifacts["differing"]
        differing = browser + rows
        shot = _screenshot(artifacts["screenshot"], bool(differing))
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
