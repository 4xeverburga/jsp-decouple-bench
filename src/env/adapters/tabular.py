"""src/harness/adapters/tabular.py — shared TSV parsing for SQL adapters.

Every SQL client is invoked with a batch/unaligned flags combination that
emits one header line then tab-separated rows, with NULL rendered as the
literal `NULL`. Keeping the parser in one place means mysql, postgres and
the generic shell adapter produce byte-identical comparisons.
"""
from __future__ import annotations

NULL = "NULL"


def parse_batch(stdout: str) -> list[dict[str, str | None]]:
    lines = [line for line in stdout.splitlines() if line]
    if not lines:
        return []
    columns = lines[0].split("\t")
    rows: list[dict[str, str | None]] = []
    for line in lines[1:]:
        values = line.split("\t")
        row: dict[str, str | None] = {}
        for index, column in enumerate(columns):
            raw = values[index] if index < len(values) else NULL
            row[column] = None if raw == NULL else (
                raw.replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")
            )
        rows.append(row)
    return rows
    
