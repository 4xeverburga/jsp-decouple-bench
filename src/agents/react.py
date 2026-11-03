"""Inspect-native ReAct agent for repository coding tasks."""

from inspect_ai.agent import Agent, react
from inspect_ai.model import Model
from inspect_ai.tool import bash, text_editor


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
