"""network_isolation — the running stack must have the shape the sample
declares. Decoupling must not introduce a hidden dependency.

Assertions (value = passed / total, all must pass):
  1. no container runs with network_mode: host
  2. every container is attached only to networks the compose file declares
  3. every published host port is one the compose file declares

Not measured in v1: outbound egress. Blocking egress is a property of the
runner's network policy, not of a gate — a gate only reads shape.
"""

from __future__ import annotations

import time
from typing import Any

import config
from src.errors import BenchError
from src.run.results import CaseResult, GateResult


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

    @staticmethod
    def _declared_ports(declared: dict[str, Any]) -> set[str]:
        ports: set[str] = set()
        for service in (declared.get("services") or {}).values():
            for entry in service.get("ports") or []:
                if (
                    isinstance(entry, dict)
                    and entry.get("published") is not None
                ):
                    ports.add(str(entry["published"]))
                elif isinstance(entry, str) and ":" in entry:
                    ports.add(entry.split(":")[-2])
        return ports

    @staticmethod
    def _published_ports(container: dict[str, Any]) -> set[str]:
        bindings = (container.get("HostConfig") or {}).get(
            "PortBindings"
        ) or {}
        return {
            str(binding["HostPort"])
            for entries in bindings.values()
            for binding in (entries or [])
            if binding.get("HostPort")
        }

    def evaluate(self) -> GateResult:
        self._started = time.monotonic()
        stack = self.ctx.stack()

        try:
            declared = stack.declared()
        except BenchError as exc:
            return self._result(
                "error", None, [], [f"compose config failed: {exc}"]
            )

        allowed_networks = set(declared.get("networks") or {}) | {"default"}
        project_networks = {
            f"{stack.project}_{name}" for name in allowed_networks
        }
        allowed_ports = self._declared_ports(declared)

        try:
            stack.up()
            containers = stack.inspect()
        except BenchError as exc:
            return self._result(
                "error", None, [], [f"stack did not come up: {exc}"]
            )
        finally:
            if not config.KEEP_STACK:
                stack.down()

        if not containers:
            return self._result(
                "error",
                None,
                [],
                ["stack is up but has no containers to inspect"],
            )

        checks: list[CaseResult] = []
        for container in containers:
            name = (container.get("Name") or "?").lstrip("/")
            service = (
                (container.get("Config") or {}).get("Labels") or {}
            ).get("com.docker.compose.service", "?")

            mode = (container.get("HostConfig") or {}).get("NetworkMode")
            checks.append(
                CaseResult(
                    case=f"{service}:network_mode",
                    verdict="pass" if mode != "host" else "fail",
                    detail=f"network_mode={mode}",
                )
            )

            attached = set(
                (
                    (container.get("NetworkSettings") or {}).get("Networks")
                    or {}
                )
            )
            extra = attached - project_networks
            checks.append(
                CaseResult(
                    case=f"{service}:networks",
                    verdict="pass" if not extra else "fail",
                    detail=(
                        "only declared networks"
                        if not extra
                        else f"joined undeclared networks {sorted(extra)}"
                    ),
                )
            )

            published = self._published_ports(container)
            undeclared = published - allowed_ports
            checks.append(
                CaseResult(
                    case=f"{service}:ports",
                    verdict="pass" if not undeclared else "fail",
                    detail=(
                        f"published {sorted(published)}"
                        if not undeclared
                        else f"undeclared host ports {sorted(undeclared)}"
                    ),
                )
            )
            if not name:  # pragma: no cover - defensive
                checks[-1].detail += " (unnamed container)"

        total = len(checks)
        passed = sum(1 for c in checks if c.verdict == "pass")
        return self._result(
            "pass" if passed == total else "fail",
            round(passed / total, 4),
            checks,
            [],
        )
