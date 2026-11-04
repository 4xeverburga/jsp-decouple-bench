"""Inspect-native ReAct agent for repository coding tasks."""

from inspect_ai.agent import Agent, as_solver, react
from inspect_ai.model import Model
from inspect_ai.solver import Solver
from inspect_ai.tool import bash, text_editor
from inspect_ai.util import message_limit

# The mock answerer never calls `submit()`, so without a cap `react` urges
# it to continue until the manifest's solve budget runs out: an hour of a
# sandbox doing nothing. A handful of messages is enough to prove the loop
# turns — system, work order, then a few replies and continue prompts.
MOCK_MESSAGE_LIMIT = 6


def solver_for(model: Model) -> Agent:
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
    """
    return react(
        model=model,
        tools=[bash(), text_editor()],
    )


def mock_solver_for(model: Model) -> Solver:
    """The same agent, capped: the smoke run of the whole pipeline.

    The cap belongs to this agent, not to a profile: it exists because
    the mock never ends a run by itself, and a real answerer must never
    inherit it. Reaching it ends the solve, not the sample: the tree is
    still captured and scored.
    """
    return as_solver(
        solver_for(model),
        limits=[message_limit(MOCK_MESSAGE_LIMIT)],
    )
