"""Scorers: one per gate, each reduced by `all_must_pass`.

- `parity.py`     functional_parity: browser artifacts and rows, compared
- `similarity.py` trace_similarity: a deterministic floor, then the judge
- `judge.py`      the model that rules, and the schema it answers in
- `judge.md`      its prompt; the bench's, never shown to the agent
"""

from .metrics import all_must_pass
from .parity import parity
from .similarity import trace_similarity

__all__ = ["all_must_pass", "parity", "trace_similarity"]
