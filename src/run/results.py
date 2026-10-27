"""src/run/results.py — the result documents. Gates build these; nothing
else constructs gate JSON by hand."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

VERDICTS = ("pass", "fail", "error", "pending")
EXIT_CODES = {"pass": 0, "fail": 1, "error": 2, "pending": 3}


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class CaseResult:
    case: str
    verdict: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        out = {"case": self.case, "verdict": self.verdict}
        if self.detail:
            out["detail"] = self.detail
        return out


@dataclass
class GateResult:
    gate_id: str
    gate_version: int
    run_id: str
    verdict: str
    value: float | None
    threshold: float
    direction: str
    duration_s: float
    details: list[CaseResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    measured_at: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        if self.verdict not in VERDICTS:
            raise ValueError(f"invalid verdict {self.verdict!r}")
        return {
            "gate_id": self.gate_id,
            "gate_version": self.gate_version,
            "run_id": self.run_id,
            "value": self.value,
            "verdict": self.verdict,
            "threshold": self.threshold,
            "direction": self.direction,
            "duration_s": round(self.duration_s, 3),
            "measured_at": self.measured_at,
            "details": [d.to_dict() for d in self.details],
            "notes": self.notes,
        }

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.verdict]
