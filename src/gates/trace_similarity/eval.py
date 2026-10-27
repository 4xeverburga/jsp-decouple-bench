"""trace_similarity — PENDING BY DESIGN.

Intent: compare captured OpenTelemetry traces with an oracle (possibly an
LLM) to detect calls that would violate the new decomposition, e.g. a
controller still reaching into the view layer, or a brand-new cross-module
call that did not exist before.

Nothing here may fabricate a score. If there are no traces, or no oracle is
configured, the verdict is `pending` and `value` is null.

Oracle contract (when it lands): a command reading the trace document on
stdin and printing `{"value": <0..1>, "notes": [...]}` on stdout.
"""
from __future__ import annotations

import json
import subprocess
import time
from typing import Any

import config
from src.run.results import CaseResult, GateResult


class TraceSimilarity:
    gate_id = "trace_similarity"

    def __init__(self, ctx: Any, definition: dict[str, Any]):
        self.ctx = ctx
        self.definition = definition
        self._started = 0.0

    def _result(self, verdict: str, value: float | None,
                details: list[CaseResult], notes: list[str]) -> GateResult:
        return GateResult(
            gate_id=self.gate_id,
            gate_version=self.definition["version"],
            run_id=self.ctx.run_id,
            verdict=verdict,
            value=value,
            threshold=self.definition["threshold"],
            direction=self.definition["direction"],
            duration_s=time.monotonic() - self._started,
            details=details,
            notes=notes,
        )

    def evaluate(self) -> GateResult:
        self._started = time.monotonic()
        traces = self.ctx.paths.traces

        if not traces.is_file():
            return self._result(
                "pending", None, [],
                [f"no trace capture for this run ({traces} absent); "
                 "the trace adapter is not implemented yet"],
            )

        if config.TRACE_ORACLE == "none" or not config.TRACE_ORACLE_CMD:
            return self._result(
                "pending", None, [],
                ["traces present but no oracle configured "
                 "(set BENCH_TRACE_ORACLE / BENCH_TRACE_ORACLE_CMD)"],
            )

        proc = subprocess.run(
            ["bash", "-c", config.TRACE_ORACLE_CMD],
            input=traces.read_text(), capture_output=True, text=True,
        )
        if proc.returncode != 0:
            return self._result(
                "error", None, [],
                [f"oracle failed ({proc.returncode}): {proc.stderr.strip()[-1000:]}"],
            )
        try:
            payload = json.loads(proc.stdout)
            value = float(payload["value"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return self._result("error", None, [],
                                [f"oracle output is not {{'value': float}}: {exc}"])

        threshold = self.definition["threshold"]
        if self.definition["direction"] == "maximize":
            passed = value >= threshold
        else:
            passed = value <= threshold
        return self._result(
            "pass" if passed else "fail",
            value,
            [CaseResult(case="oracle", verdict="pass" if passed else "fail",
                        detail=f"value={value} threshold={threshold}")],
            list(payload.get("notes") or []),
        )
