"""network_isolation — the stack's declared topology, read statically.

No container is started: both compose files are rendered with `compose
config` and compared, so the gate costs ~0.1 s and cannot be confused by
an app that fails to boot. Topology is declarative, and `config` already
resolves substitution, override files, `external:` and `name:`.

The contract is the PINNED file (`git show <commit_sha>:compose.yaml`),
never the worktree one: an agent that adds a network or a published port
must not thereby widen the allowance it is graded against.

Assertions (value = passed / total, all must pass):
  1. no service declares `network_mode:` (`host` or `service:`)
  2. every service attaches only to networks the pin declares
  3. every service publishes only the ports the pin declares for it
  4. db attaches to exactly the pin's networks
  5. `front` shares no network with db — this is the task

The pin attaches `front` to the backend network on purpose (the pristine
app is server-rendered and reads the database directly), so an untouched
tree fails 5 and only real work can make it pass.

What this cannot see is anything a container does at run time. That is
the runner's network policy, not a gate — a gate only reads shape.
"""

from __future__ import annotations

import time
from typing import Any

from src.errors import BenchError, NotFoundError
from src.run.results import CaseResult, GateResult

FRONT_SERVICE = "front"


def _networks(rendered: dict[str, Any], service: str) -> set[str]:
    spec = (rendered.get("services") or {}).get(service) or {}
    return set(spec.get("networks") or {})


def _ports(rendered: dict[str, Any], service: str) -> set[str]:
    spec = (rendered.get("services") or {}).get(service) or {}
    ports: set[str] = set()
    for entry in spec.get("ports") or []:
        if isinstance(entry, dict):
            if entry.get("published") is not None:
                ports.add(str(entry["published"]))
        elif isinstance(entry, str) and ":" in entry:
            ports.add(entry.split(":")[-2])
    return ports


def _escaped(mode: str) -> bool:
    return mode == "host" or mode.startswith("service:")


class NetworkIsolation:
    gate_id = "network_isolation"

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

    def evaluate(self) -> GateResult:
        self._started = time.monotonic()
        stack = self.ctx.stack()

        try:
            db_service = self.ctx.binding("db")["options"]["service"]
        except (KeyError, NotFoundError) as exc:
            return self._result(
                "error", None, [], [f"no db service bound: {exc}"]
            )

        try:
            contract = stack.declared_pinned()
            current = stack.declared()
        except BenchError as exc:
            return self._result(
                "error", None, [], [f"compose config failed: {exc}"]
            )

        allowed = set(contract.get("networks") or {})
        checks: list[CaseResult] = []
        for name in sorted(current.get("services") or {}):
            mode = current["services"][name].get("network_mode") or ""
            checks.append(
                CaseResult(
                    case=f"{name}:network_mode",
                    verdict="fail" if _escaped(mode) else "pass",
                    detail=f"network_mode={mode or 'none'}",
                )
            )

            attached = _networks(current, name)
            extra = attached - allowed
            checks.append(
                CaseResult(
                    case=f"{name}:networks",
                    verdict="fail" if extra else "pass",
                    detail=(
                        f"attached {sorted(attached)}"
                        if not extra
                        else f"undeclared networks {sorted(extra)}"
                    ),
                )
            )

            published = _ports(current, name)
            undeclared = published - _ports(contract, name)
            checks.append(
                CaseResult(
                    case=f"{name}:ports",
                    verdict="fail" if undeclared else "pass",
                    detail=(
                        f"published {sorted(published)}"
                        if not undeclared
                        else f"undeclared host ports {sorted(undeclared)}"
                    ),
                )
            )

        services = current.get("services") or {}
        missing = ""
        if FRONT_SERVICE not in services:
            missing = FRONT_SERVICE
        elif db_service not in services:
            missing = db_service

        shared = _networks(current, FRONT_SERVICE) & _networks(
            current, db_service
        )
        if missing:
            reason = f"{missing} is missing"
        elif shared:
            reason = f"shares {sorted(shared)} with {db_service}"
        else:
            reason = f"shares no network with {db_service}"
        checks.append(
            CaseResult(
                case=f"{FRONT_SERVICE}:isolated_from_db",
                verdict="fail" if missing or shared else "pass",
                detail=reason,
            )
        )

        database = _networks(current, db_service)
        widened = database - _networks(contract, db_service)
        checks.append(
            CaseResult(
                case=f"{db_service}:networks_unchanged",
                verdict="fail" if widened or not database else "pass",
                detail=(
                    f"attached {sorted(database)}"
                    if not widened
                    else f"the database joined {sorted(widened)}"
                ),
            )
        )

        total = len(checks)
        passed = sum(1 for c in checks if c.verdict == "pass")
        return self._result(
            "pass" if passed == total else "fail",
            round(passed / total, 4),
            checks,
            [],
        )
