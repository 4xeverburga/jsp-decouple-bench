"""src/harness/adapters/pristine.py — the self-check harness.

No agent runs, so the tree stays at the pinned commit and the diff is
empty. This is what proves the gates reproduce the goldens: a `pristine`
run must pass `functional_parity`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.harness.ports import HarnessResult, HarnessTask


class PristineHarness:
    name = "pristine"

    def __init__(self, options: dict[str, Any] | None = None):
        self.options = options or {}

    def run(self, task: HarnessTask, log_dir: Path) -> HarnessResult:
        log = Path(log_dir) / "harness.log"
        log.write_text(f"pristine: no agent, nothing to do\n{task.render()}")
        return HarnessResult(exit_code=0, duration_s=0.0, log_path=log)
