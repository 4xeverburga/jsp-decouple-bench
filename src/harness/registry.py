"""src/harness/registry.py — build the one harness.

There is no adapter per agent, and no name→command table either: a harness
**is the command you give it**, and the prompt arrives on stdin. Which CLI
(opencode, claude, copilot, …), which model, and which effort variant are
therefore argv — recorded verbatim in the run's `harness.json` — and never a
Python class.

`label` is free text that lands in `TASK_RUN.harness`: it names the run, it
selects nothing.
"""

from __future__ import annotations

import config
from src.harness.adapters.command import CommandHarness
from src.harness.ports import HarnessPort


def resolve(label: str, cmd: str | None) -> HarnessPort:
    """The per-run command wins; otherwise `.env`'s BENCH_HARNESS_CMD."""
    return CommandHarness(label, cmd or config.HARNESS_CMD)
