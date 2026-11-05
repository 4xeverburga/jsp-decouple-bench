"""trace_similarity as a scorer: did the work move behind the boundary?

`functional_parity` proves the browser cannot tell the difference, which a
tree that changed nothing also passes. This gate reads how the app served
the same flow: the spans the replay kept (`src/bench/replay.py`), condensed
the same way as the case's trace base, and judged against it.

Two steps, cheapest first:

1. **A floor, deterministic.** A tree in which no request was answered by
   the app's own server over HTTP has no boundary at all — that is what a
   no-op looks like — and fails without asking anyone.
2. **The judge** (`judge.py`), with the score profile's model, for the
   rest: whether the work of the requests the manifest puts in scope
   (`scope.trace`) now runs behind the hop, and whether their writes still
   happen.

A case with no spans, or no trace base, or a judge that answers no verdict,
raises: it was not measured, and the run must say so instead of passing.
"""

from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, scorer
from inspect_ai.solver import TaskState

import settings

from ..metrics import all_must_pass
from ..observation import observation
from . import base, judge, spans

MOVES = ("all", "writes")


def _scope(case: str, entries: list[dict], before: list[dict]) -> str:
    """The case's scope as the judge reads it, checked against its base.

    A line the base does not have is a stale scope, from before a
    recapture or a flow change: it fails here, by name, rather than leave
    the judge a request it cannot find.
    """
    labels = {request["label"] for request in before}
    lines = []
    for entry in entries:
        if entry["request"] not in labels:
            raise KeyError(
                f"{case}: scope names {entry['request']!r}, which its trace "
                f"base has no request for"
            )
        if entry["move"] not in MOVES:
            raise ValueError(
                f"{case}: scope move {entry['move']!r} is not one of {MOVES}"
            )
        lines.append(f"- {entry['request']}    move: {entry['move']}")
    return "\n".join(lines)


@scorer(metrics=[all_must_pass()])
def trace_similarity(
    slug: str, scope: dict, profile_name: str, profile: dict
) -> scorer:
    """Judge the case's spans against its base, with the profile's judge.

    `scope` is the manifest's `scope.trace`: per case, the requests whose
    work must move. The profile is passed as data, its name beside it, so
    the run's log records which model ruled and how.
    """

    async def score(state: TaskState, target_state: Target) -> Score:
        seen = observation(state)
        case = seen["case"]
        if seen["trace"] is None:
            raise RuntimeError(
                f"{case}: the replay kept no spans, so the boundary cannot "
                f"be judged; is the stack's collector running?"
            )
        before = base.read(slug, case)
        after = spans.condense(spans.read(settings.ROOT / seen["trace"]))
        hops = spans.loopback_calls(after)
        facts = {
            "case": case,
            "trace": seen["trace"],
            "loopback_calls": hops,
            "score_profile": profile_name,
        }
        if hops == 0:
            return Score(
                value=INCORRECT,
                answer=case,
                explanation=(
                    f"{case}=no-boundary: no request was answered by the "
                    f"app itself over HTTP"
                ),
                metadata=facts,
            )

        if case not in scope:
            raise KeyError(
                f"{case}: the manifest's scope.trace declares no requests "
                f"for it, so there is nothing to judge"
            )
        text = judge.prompt(
            state.input_text,
            _scope(case, scope[case], before),
            spans.render(before),
            spans.render(after),
        )
        verdict, model = await judge.rule(profile, text)
        failed = [
            name for name in judge.CRITERIA if not getattr(verdict, name)
        ]
        return Score(
            value=INCORRECT if failed else CORRECT,
            answer=case,
            explanation=(
                f"{case}=pass: {verdict.explanation}"
                if not failed
                else f"{case}=fails:{','.join(failed)}: {verdict.explanation}"
            ),
            metadata={
                **facts,
                "judge_model": model,
                "verdict": verdict.model_dump(),
            },
        )

    return score
