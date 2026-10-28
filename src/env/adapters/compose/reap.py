"""src/env/adapters/compose/reap.py — leave nothing running behind a run.

Compose stamps every container, network and volume it creates with
`com.docker.compose.project` and `com.docker.compose.project.working_dir`,
so discovery is a label query over the run's own tree rather than a lookup
by project name. The name is not enough: an agent that runs
`docker compose up` in its checkout gets the directory's default project
name, and that stack is still the run's to remove.

Plain `docker` verbs, not `docker compose down`: the compose file belongs
to the agent and may have been edited or deleted by the time the run ends,
and teardown must not depend on it.

Everything is scoped to one `location`. Every run owns its own folder, so a
concurrent run's stack can never be touched.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import config
from src.run.process import ProcessRun, run_streamed

WORKING_DIR_LABEL = "com.docker.compose.project.working_dir"
PROJECT_LABEL = "com.docker.compose.project"

# SIGTERM first, so a database closes its files; `rm --force` ends whatever
# ignored it.
STOP_GRACE_S = 10
# A wedged daemon must not hang a finished run forever.
TEARDOWN_TIMEOUT_S = 120


def _docker(argv: list[str], logger: logging.Logger) -> ProcessRun:
    return run_streamed(
        [config.DOCKER, *argv],
        cwd=config.ROOT,
        env=dict(os.environ),
        stdin_text=None,
        timeout_s=TEARDOWN_TIMEOUT_S,
        heartbeat_s=config.LOG_HEARTBEAT_S,
        logger=logger,
        sink=None,
        echo=False,
    )


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _by_working_dir(
    query: tuple[str, ...],
    location: Path,
    template: str,
    logger: logging.Logger,
) -> list[str]:
    run = _docker(
        [
            *query,
            "--filter",
            f"label={WORKING_DIR_LABEL}={location}",
            "--format",
            template,
        ],
        logger,
    )
    return _lines(run.stdout)


def _by_project(
    query: tuple[str, ...],
    project: str,
    template: str,
    logger: logging.Logger,
) -> list[str]:
    run = _docker(
        [
            *query,
            "--filter",
            f"label={PROJECT_LABEL}={project}",
            "--format",
            template,
        ],
        logger,
    )
    return _lines(run.stdout)


def _projects(location: Path, logger: logging.Logger) -> list[str]:
    """Every compose project that created anything under `location`."""
    template = f'{{{{.Label "{PROJECT_LABEL}"}}}}'
    found: set[str] = set()
    for query in (
        ("ps", "-a"),
        ("network", "ls"),
        ("volume", "ls"),
    ):
        found.update(_by_working_dir(query, location, template, logger))
    return sorted(found)


def _teardown(project: str, logger: logging.Logger) -> None:
    """Containers, then networks, then volumes — the dependency order."""
    containers = _by_project(("ps", "-a"), project, "{{.ID}}", logger)
    if containers:
        _docker(
            ["container", "stop", "--time", str(STOP_GRACE_S), *containers],
            logger,
        )
        _docker(["container", "rm", "--force", *containers], logger)
    networks = _by_project(("network", "ls"), project, "{{.ID}}", logger)
    if networks:
        _docker(["network", "rm", *networks], logger)
    volumes = _by_project(("volume", "ls"), project, "{{.Name}}", logger)
    if volumes:
        _docker(["volume", "rm", *volumes], logger)


def reap(location: Path, logger: logging.Logger) -> int:
    """Take down every compose project rooted in `location`.

    Returns how many projects were removed. Nothing left over is the normal
    case (the run's own `down` came first); whatever survives is logged as
    an error, because a leaked stack keeps its host ports and the next run
    cannot have them.
    """
    projects = _projects(location, logger)
    for project in projects:
        logger.info("reaping compose project %s in %s", project, location)
        _teardown(project, logger)
    remaining = _projects(location, logger)
    if remaining:
        logger.error(
            "still running in %s after teardown: %s",
            location,
            ", ".join(remaining),
        )
    return len(projects)
