"""Agent implementations used by the solve phase.

Every agent the solve can run is one row of ``registry.AGENTS``, the
native one included, so a name is resolved in one place and no caller has
to know which kind of agent it is holding.
"""

from .registry import solver_for, state

__all__ = ["solver_for", "state"]
