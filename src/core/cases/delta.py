"""functional_parity/delta.py — before/after table deltas.

Ported verbatim in behaviour from the pre-rewrite capture tooling: the
`expected_delta.json` files were produced by exactly this algorithm, so the
comparison stays meaningful.
"""

from __future__ import annotations

import json
from typing import Any


def canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True)


def _sort(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: canonical(row))


def delta_table(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    key_columns: list[str],
    ignore_columns: list[str],
) -> dict[str, Any]:
    ignored = set(ignore_columns or [])
    strip = lambda row: {c: v for c, v in row.items() if c not in ignored}  # noqa: E731
    key_of = lambda row: canonical([row.get(c) for c in key_columns])  # noqa: E731

    before_by_key = {key_of(r): r for r in before}
    after_by_key = {key_of(r): r for r in after}

    inserted, deleted, updated = [], [], []
    for key, row in after_by_key.items():
        if key not in before_by_key:
            inserted.append(strip(row))
        else:
            previous = before_by_key[key]
            changes = {
                column: [previous.get(column), value]
                for column, value in row.items()
                if column not in ignored and previous.get(column) != value
            }
            if changes:
                updated.append(
                    {
                        "key": {c: row.get(c) for c in key_columns},
                        "changes": changes,
                    }
                )
    for key, row in before_by_key.items():
        if key not in after_by_key:
            deleted.append(strip(row))

    return {
        "key_columns": list(key_columns),
        "ignore_columns": sorted(ignored),
        "inserted": _sort(inserted),
        "updated": _sort(updated),
        "deleted": _sort(deleted),
    }


def summary(actual: Any, expected: Any, limit: int = 3) -> str:
    """Short, human-readable reason for a mismatch."""
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return "shape differs"
    problems = []
    actual_tables = actual.get("tables") or {}
    expected_tables = expected.get("tables") or {}
    for name in sorted(set(actual_tables) | set(expected_tables)):
        mine = canonical(actual_tables.get(name))
        theirs = canonical(expected_tables.get(name))
        if mine != theirs:
            parts = []
            for bucket in ("inserted", "updated", "deleted"):
                a = len((actual_tables.get(name) or {}).get(bucket) or [])
                e = len((expected_tables.get(name) or {}).get(bucket) or [])
                if a != e:
                    parts.append(f"{bucket} {a}!={e}")
            problems.append(f"{name}({', '.join(parts) or 'values differ'})")
        if len(problems) >= limit:
            break
    return "; ".join(problems) or "values differ"
