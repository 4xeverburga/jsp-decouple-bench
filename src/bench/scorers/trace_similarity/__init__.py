"""trace_similarity: the gate on how the app served the flow.

- `similarity.py` the scorer: a deterministic floor, then the judge
- `spans.py`      the collector's OTLP file, condensed to a request tree
- `base.py`       the case's trace base, frozen beside `expect.json`
- `judge.py`      the model that rules, and the schema it answers in
- `judge.md`      its prompt; the bench's, never shown to the agent
"""

from .similarity import trace_similarity

__all__ = ["trace_similarity"]
