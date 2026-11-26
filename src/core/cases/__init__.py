"""The machinery that plays and grades a case; nothing else reads its layout.

Cases are data in `samples/<sample>/cases/`; this package only plays them.

- `cases.py`     play a case's flow, read and compare its frozen golden
- `delta.py`     before/after table deltas, the algorithm the goldens froze
- `db.py`        table snapshots through the case's stack
- `tabular.py`   the TSV parser every SQL adapter shares
- `artifacts.py` the normalizer (base URL, clocks, inline styles)
"""
