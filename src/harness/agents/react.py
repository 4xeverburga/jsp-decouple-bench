"""Inspect-native ReAct agent for repository coding tasks."""

from inspect_ai.agent import Agent, as_solver, react
from inspect_ai.model import ChatMessage, Model
from inspect_ai.model._compaction import CompactionAuto
from inspect_ai.solver import Solver
from inspect_ai.tool import bash, text_editor
from inspect_ai.util import message_limit

# The mock answerer never calls `submit()`, so without a cap `react` urges
# it to continue until the manifest's solve budget runs out: an hour of a
# sandbox doing nothing. A handful of messages is enough to prove the loop
# turns — system, work order, then a few replies and continue prompts.
MOCK_MESSAGE_LIMIT = 6


COMPACTIONS = frozenset({"none", "CompactionAuto"})


class ContextOverflowError(RuntimeError):
    """The conversation outgrew the answerer's window and was not saved."""


async def _refuse_overflow(messages: list[ChatMessage]) -> list[ChatMessage]:
    """Fail the sample where react would otherwise end it quietly.

    react calls its truncation filter on `model_length` when there is no
    compaction, and when a forced compaction failed. Its own default for
    both is to log an `info` and return, so the solve ends as if finished
    and a half-done tree is scored. Raising here makes it an `error`.
    """
    raise ContextOverflowError(
        f"context window exceeded at {len(messages)} messages and not "
        f"compacted: the solve did not finish, its tree is not a result"
    )


def solver_for(
    model: Model,
    compaction: str,
    context_window: int,
    compaction_threshold: float | str,
) -> Agent:
    """Build a ReAct agent with shell and text-file editing tools.

    No ``prompt``: the task is the work order, which Inspect hands the
    model as the sample's input, so an instructions override here would
    only restate it — and the work order says it better, because it is
    the manifest's own ask. ``react``'s default prompt is still needed,
    and is why ``prompt=None`` is not the answer either: it is the only
    place that tells the model the tool loop exists and that the run ends
    by calling ``submit()``. Passing a string replaces that default's
    ``instructions`` slot and keeps the rest, which is what put a second,
    weaker copy of the requirements in front of the model — and made this
    the one backend carrying it, since every CLI brings its own.

    ``compaction`` is the profile's explicit choice: ``none`` keeps
    react's default of remembering everything, ``CompactionAuto`` compacts
    once the input passes ``compaction_threshold`` of ``context_window``.
    The threshold is handed over in tokens, so Inspect never looks the
    window up itself. An overflow that is not compacted fails the sample.
    """
    if compaction not in COMPACTIONS:
        raise ValueError(
            f"unknown compaction {compaction!r}: "
            f"expected one of {sorted(COMPACTIONS)}"
        )
    strategy = None
    if compaction == "CompactionAuto":
        strategy = CompactionAuto(
            threshold=int(compaction_threshold * context_window)
        )
    return react(
        model=model,
        tools=[bash(), text_editor()],
        compaction=strategy,
        truncation=_refuse_overflow,
    )


def mock_solver_for(
    model: Model,
    compaction: str,
    context_window: int,
    compaction_threshold: float | str,
) -> Solver:
    """The same agent, capped: the smoke run of the whole pipeline.

    The cap belongs to this agent, not to a profile: it exists because
    the mock never ends a run by itself, and a real answerer must never
    inherit it. Reaching it ends the solve, not the sample: the tree is
    still captured and scored.
    """
    return as_solver(
        solver_for(model, compaction, context_window, compaction_threshold),
        limits=[message_limit(MOCK_MESSAGE_LIMIT)],
    )
