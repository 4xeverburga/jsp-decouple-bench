"""src/run/ids.py — run identity. Never a timestamp: two runs may start in
the same second, and a timestamp would also write kernel/host clock into
every artifacts path."""
from __future__ import annotations

import uuid


def new_run_id() -> str:
    return uuid.uuid4().hex
