"""functional_parity: the gate, and the machinery that grades a case.

Cases are data in `src/samples/<sample>/cases/`; this package only plays them.
Nothing else reads the case layout.

- `parity.py`    the scorer: browser artifacts and database rows, compared
- `cases.py`     play a case's flow, read its frozen golden
- `delta.py`     before/after table deltas, the algorithm the goldens froze
- `db.py`        table snapshots through the case's stack
- `tabular.py`   the TSV parser every SQL adapter shares
- `artifacts.py` the normalizer (base URL, clocks, inline styles)
"""

from .parity import parity

__all__ = ["parity"]
