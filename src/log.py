"""src/log.py — the operator's view of what a run is doing.

Stdlib `logging` only, configured in exactly one place: `setup()` is called
once at the entry point (`main.py`) with `config.LOG_LEVEL`.

Everything goes to **stderr**, because stdout carries the one
machine-readable value a command produces (a run_id) and must stay
parseable. A step that prints nothing is indistinguishable from a hung
process, so the modules that shell out or poll (harness, stack, gates)
log every transition — and the runs take tens of minutes.
"""

from __future__ import annotations

import logging
import sys

# Time of day, no date: a run lives in minutes and its directory already
# records the date.
FORMAT = "%(asctime)s %(levelname)-7s %(name)-26s %(message)s"
DATEFMT = "%H:%M:%S"


def setup(level: str) -> None:
    """Install the single stderr handler. Idempotent; the last call wins."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(FORMAT, DATEFMT))
    root.addHandler(handler)
    root.setLevel(level.upper())


def get(name: str) -> logging.Logger:
    """A module's logger, all under the `bench.` namespace."""
    return logging.getLogger(f"bench.{name}")
