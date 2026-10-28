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

    def reap(self) -> int:
        """Tear down anything this run's tree left running.

        By location, not by project name: whatever `docker compose up` the
        agent left in its own checkout has to go too. Returns the number of
        projects removed; nothing running is not an error.
        """

    def base_url(self) -> str: ...

    def ps(self) -> list[dict[str, Any]]: ...

    def declared_pinned(self) -> dict[str, Any]:
        """`compose config` of the PINNED compose file, normalised.

        Rendered from `SAMPLE.commit_sha`, never from the worktree, so a
        gate is never graded against the allowance the agent wrote.
        """

    def declared(self) -> dict[str, Any]:
        """`compose config` of the worktree compose file — the submission.

        Same project and run ports as `declared_pinned`, so the two
        documents are directly comparable. Starts no container.
        """

    def exec_(
        self, service: str, argv: list[str], stdin: str | None = None
    ) -> str: ...


@runtime_checkable
class BrowserPort(Protocol):
    """Executes a flow file (a case's Playwright script).

    Takes the path, not a case name: adapters know nothing about where the
    corpus lives.
    """

    def run_case(
        self,
        flow_path: Path,
        base_url: str,
        e2e: dict[str, Any],
        failure_png: Path,
    ) -> dict[str, Any]: ...

    def capture_case(
        self,
        flow_path: Path,
        base_url: str,
        e2e: dict[str, Any],
        images_dir: Path,
    ) -> dict[str, Any]: ...


@runtime_checkable
class DatabasePort(Protocol):
    """Reads the sample DB in a comparable, order-free form."""

    def list_tables(self) -> list[str]: ...

    def dump(self, table: str) -> list[dict[str, Any]]: ...

    def dump_many(
        self, tables: list[str]
    ) -> dict[str, list[dict[str, Any]]]: ...
