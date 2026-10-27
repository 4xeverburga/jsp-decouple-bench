"""src/harness/ports.py — the capabilities a task or a gate may ask for.

Gates and tasks depend on these protocols only; the concrete adapter is
selected per run from TASK_MANIFEST.bindings_json (by technology).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StackPort(Protocol):
    """A startable application stack (one compose file, one project name)."""

    def up(self) -> str:
        """Start and wait for health; return the base URL."""

    def down(self, volumes: bool = True) -> None: ...

    def reset(self) -> str:
        """down -v && up; used between cases so ids are deterministic."""

    def base_url(self) -> str: ...

    def ps(self) -> list[dict[str, Any]]: ...

    def inspect(self) -> list[dict[str, Any]]:
        """Raw `docker inspect` JSON for every container of the project."""

    def declared(self) -> dict[str, Any]:
        """`docker compose config` normalised: services, networks, ports."""

    def exec_(self, service: str, argv: list[str], stdin: str | None = None) -> str: ...


@runtime_checkable
class BrowserPort(Protocol):
    """Executes a case's Playwright flow."""

    def run_case(self, case_name: str, base_url: str) -> dict[str, Any]: ...

    def capture_case(self, case_name: str, base_url: str,
                     images_dir: Path) -> dict[str, Any]: ...


@runtime_checkable
class DatabasePort(Protocol):
    """Reads the sample DB in a comparable, order-free form."""

    def list_tables(self) -> list[str]: ...

    def dump(self, table: str) -> list[dict[str, Any]]: ...

    def dump_many(self, tables: list[str]) -> dict[str, list[dict[str, Any]]]: ...
