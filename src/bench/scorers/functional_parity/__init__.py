"""functional_parity: the gate, its corpus, and the machinery under both.

A case is a functional-parity test, so it lives inside the package that
grades it — flow, golden, and the `corpus/` they sit in. Nothing outside
this package reads the corpus layout.

- `parity.py`    the scorer: browser artifacts and database rows, compared
- `cases.py`     play a case's flow, read its frozen golden
- `delta.py`     before/after table deltas, the algorithm the goldens froze
- `db.py`        table snapshots through `sandbox()`
- `tabular.py`   the TSV parser every SQL adapter shares
- `artifacts.py` the normalizer (base URL, clocks, inline styles)
"""

from .parity import parity

__all__ = ["parity"]
