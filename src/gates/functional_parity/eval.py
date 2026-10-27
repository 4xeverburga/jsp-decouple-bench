"""functional_parity — replay each case, compare its DB delta and artifacts
against the frozen golden.

value        = passed_cases / total_cases
verdict      = pass only if every case passes; error only if no case could
               even be measured (stack down, DB unreachable).
"""
from __future__ import annotations

import time
from typing import Any

import config
from src.gates.functional_parity.delta import canonical, delta_table, summary
from src.run.results import CaseResult, GateResult


class FunctionalParity:
    gate_id = "functional_parity"

    def __init__(self, ctx: Any, definition: dict[str, Any]):
        self.ctx = ctx
        self.definition = definition
        self._started = 0.0

    # --- result helper -------------------------------------------------------
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

    # --- one case ------------------------------------------------------------
    def _case(self, name: str) -> CaseResult:
        try:
            case = self.ctx.case(name)
            expect = self.ctx.expect(name)
            tables = (case.get("db") or {}).get("tables") or []

            stack = self.ctx.stack()
            database = self.ctx.adapter("db")
            browser = self.ctx.adapter("browser")

            stack.reset()
            base_url = self.ctx.base_url()
            table_names = [t["name"] for t in tables]
            before = database.dump_many(table_names)
            artifacts = browser.run_case(name, base_url)
            after = database.dump_many(table_names)

            actual = {"tables": {
                t["name"]: delta_table(
                    before.get(t["name"]) or [],
                    after.get(t["name"]) or [],
                    t.get("key_columns") or ["id"],
                    t.get("ignore_columns") or [],
                )
                for t in tables
            }}

            problems: list[str] = []
            if canonical(actual) != canonical(expect.get("db")):
                problems.append("db: " + summary(actual, expect.get("db")))

            expected_artifacts = expect.get("artifacts") or {}
            for key in (case.get("e2e") or {}).get("artifacts") or []:
                if canonical(artifacts.get(key)) != canonical(expected_artifacts.get(key)):
                    problems.append(f"artifact {key!r} differs")

            return CaseResult(
                case=name,
                verdict="fail" if problems else "pass",
                detail="; ".join(problems),
            )
        except Exception as exc:  # a broken case must not hide the others
            return CaseResult(case=name, verdict="error",
                              detail=f"{type(exc).__name__}: {exc}")

    # --- GateInputPort -------------------------------------------------------
    def evaluate(self) -> GateResult:
        self._started = time.monotonic()
        cases = list(self.ctx.scope.get("cases") or [])
        if not cases:
            return self._result("error", None, [], ["manifest scope lists no cases"])

        stack = self.ctx.stack()
        details: list[CaseResult] = []
        try:
            for name in cases:
                details.append(self._case(name))
        finally:
            if not config.KEEP_STACK:
                stack.down()

        total = len(details)
        passed = sum(1 for d in details if d.verdict == "pass")
        measured = [d for d in details if d.verdict != "error"]

        if passed == total:
            return self._result("pass", 1.0, details, [])
        if not measured:
            # nothing could be measured: a number here would be a lie
            return self._result("error", None, details, [])
        return self._result("fail", round(passed / total, 4), details, [])
