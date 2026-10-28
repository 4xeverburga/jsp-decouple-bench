"""src/run/paths.py — one directory per run, keyed by run_id. Nothing else
in the artifacts tree is shared between runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import config


@dataclass(frozen=True)
class RunPaths:
    run_id: str
    root: Path

    @classmethod
    def create(cls, run_id: str) -> "RunPaths":
        root = Path(config.RUNS_DIR) / run_id
        root.mkdir(parents=True, exist_ok=False)
        return cls(run_id=run_id, root=root)

    @classmethod
    def load(cls, run_id: str) -> "RunPaths":
        return cls(run_id=run_id, root=Path(config.RUNS_DIR) / run_id)

    @property
    def task_json(self) -> Path:
        return self.root / "task.json"

    @property
    def diff_patch(self) -> Path:
        return self.root / "diff.patch"

    @property
    def harness(self) -> Path:
        return self.root / "harness.json"

    @property
    def images(self) -> Path:
        return self.root / "images"

    def images_for(self, gate_id: str) -> Path:
        """Screenshots one gate kept — a directory per gate.

        `images/` itself is where `case-capture` stages step shots; a gate
        that keeps evidence writes below its own name so two gates can
        never overwrite each other's case names.
        """
        return self.images / gate_id

    @property
    def traces(self) -> Path:
        return self.root / "traces.json"

    def gate(self, gate_id: str) -> Path:
        return self.root / "gates" / f"{gate_id}.json"

    def case(self, case: str) -> Path:
        """Per-case gate output — the cross-gate interface."""
        return self.root / "cases" / f"{case}.json"
