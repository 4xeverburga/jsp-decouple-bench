"""src/harness/ports.py — the agent harness boundary.

A harness receives **the prompt** and does the work: it is the agent, or
the thing that drives one.

The agent must not know it is being evaluated. This module is where that
rule is enforced, structurally:

- the prompt is the manifest prompt **verbatim** — no routes, no case
  names, no goldens, no "benchmark"/"evaluation" vocabulary;
- everything else in `HarnessTask` is plumbing for the harness *process*
  and is never rendered into the text the agent reads;
- verification metadata (`TASK_MANIFEST.scope_json`) never enters this
  dataclass at all, so it cannot leak by accident.

The supervisor — a consumer of this bench — is the party that knows about
grading. The agent just gets a work order in a repository.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class HarnessTask:
    prompt: str
    cwd: Path

    def render(self) -> str:
        """Exactly what the agent reads, and nothing more."""
        return self.prompt.rstrip("\n") + "\n"


@dataclass
class HarnessResult:
    exit_code: int
    duration_s: float
    cost_usd: float | None = None
    tokens: int | None = None
    log_path: Path | None = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def to_dict(self) -> dict:
        return {
            "exit_code": self.exit_code,
            "duration_s": round(self.duration_s, 3),
            "cost_usd": self.cost_usd,
            "tokens": self.tokens,
            "log": str(self.log_path) if self.log_path else None,
        }


@runtime_checkable
class HarnessPort(Protocol):
    name: str

    def run(self, task: HarnessTask, log_dir: Path) -> HarnessResult:
        """Execute the prompt in `task.cwd`; leave the tree as it stands."""
