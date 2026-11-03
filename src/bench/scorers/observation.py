"""Where the score phase's replay leaves what it saw, for every scorer.

A leaf on purpose: the replay (`src/bench/replay.py`) writes it and the
scorers read it, and neither may import the other.
"""

from inspect_ai.solver import TaskState

STORE_KEY = "replay"


def observation(state: TaskState) -> dict:
    """What the replay saw, for a scorer. Absent is a wiring error."""
    seen = state.store.get(STORE_KEY)
    if seen is None:
        raise RuntimeError(
            "no replay in the sample's store: the score phase's solver must "
            "be replayed_case"
        )
    return seen
