"""Scorers: one per gate, each reduced by `all_must_pass`."""

from .functional_parity import parity
from .metrics import all_must_pass

__all__ = ["all_must_pass", "parity"]
