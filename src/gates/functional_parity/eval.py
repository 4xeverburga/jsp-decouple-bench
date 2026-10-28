"""functional_parity — replay each case, compare its DB delta and artifacts
against the frozen golden, and **log every case result** so other gates can
consume it (`out/runs/<run_id>/cases/<case>.json`) without touching the
corpus.

value   = passed_cases / total_cases
verdict = pass only if every case passes; error only if no case could be
          measured at all (stack down, fixture corrupt). A flow that
          asserts the graded behaviour and does not see it is a *fail*:
          it measured the app and the app did the wrong thing.
"""

from __future__ import annotations

import time
from typing import Any

import config
from src.gates.functional_parity import corpus
from src.gates.functional_parity.artifacts import normalize
from src.gates.functional_parity.delta import canonical, delta_table, summary
from src.run.atomic import write_json
from src.run.results import CaseResult, GateResult


class FunctionalParity:
    gate_id = "functional_parity"

    def __init__(self, ctx: Any, definition: dict[str, Any]):
        self.ctx = ctx
        self.definition = definition
        self._started = 0.0

    def _result(
        self,
        verdict: str,
        value: float | None,
        details: list[CaseResult],
        notes: list[str],
    ) -> GateResult:
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

    def _case(self, name: str) -> CaseResult:
        sample = self.ctx.sample["slug"]
        started = time.monotonic()
        record: dict[str, Any] = {"case": name, "sample": sample}
        try:
            case = corpus.contract(sample, name)
            e2e = case.get("e2e") or {}
            expect = corpus.golden(sample, name)
            tables = (case.get("db") or {}).get("tables") or []

            stack = self.ctx.stack()
            database = self.ctx.adapter("db")
            browser = self.ctx.adapter("browser")

            stack.reset()
            base_url = self.ctx.base_url()
            columns = [t["name"] for t in tables]
            before = database.dump_many(columns)
            artifacts = browser.run_case(
                corpus.flow(sample, name), base_url, e2e
            )
            artifacts = normalize(artifacts, base_url)
            after = database.dump_many(columns)

            actual = {
                "tables": {
                    t["name"]: delta_table(
                        before.get(t["name"]) or [],
                        after.get(t["name"]) or [],
                        t.get("key_columns") or ["id"],
                        t.get("ignore_columns") or [],
                    )
                    for t in tables
                }
            }

            problems: list[str] = []
            if canonical(actual) != canonical(expect.get("db")):
                problems.append("db: " + summary(actual, expect.get("db")))
            expected_artifacts = expect.get("artifacts") or {}
            for key in e2e.get("artifacts") or []:
                if canonical(artifacts.get(key)) != canonical(
                    expected_artifacts.get(key)
                ):
                    problems.append(f"artifact {key!r} differs")

            record.update(
                verdict="fail" if problems else "pass",
                detail="; ".join(problems),
                artifacts=artifacts,
                db=actual,
            )
        except AssertionError as exc:  # the graded behaviour was not met
            record.update(
                verdict="fail",
                detail=str(exc) or "flow assertion failed",
            )
        except Exception as exc:  # a broken case must not hide the others
            record.update(
                verdict="error", detail=f"{type(exc).__name__}: {exc}"
            )

        record["duration_s"] = round(time.monotonic() - started, 3)
        # The cross-gate interface: results are logged, the corpus stays
        # private.
        write_json(self.ctx.paths.case(name), record)
        return CaseResult(
            case=name,
            verdict=record["verdict"],
            detail=record.get("detail", ""),
        )

    def evaluate(self) -> GateResult:
        self._started = time.monotonic()
        cases = list(self.ctx.scope.get("cases") or [])
        if not cases:
            return self._result(
                "error", None, [], ["manifest scope lists no cases"]
            )

        stack = self.ctx.stack()
        details: list[CaseResult] = []
        try:
            for name in cases:
                details.append(self._case(name))
        finally:
            if not config.KEEP_STACK:
                stack.down()

        passed = sum(1 for d in details if d.verdict == "pass")
        if passed == len(details):
            return self._result("pass", 1.0, details, [])
        if all(d.verdict == "error" for d in details):
            return self._result("error", None, details, [])
        return self._result(
            "fail", round(passed / len(details), 4), details, []
        )
