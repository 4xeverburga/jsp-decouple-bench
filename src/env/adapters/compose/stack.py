"""src/harness/adapters/compose/stack.py — `compose@1` → StackPort.

Technology-neutral: it only needs the sample commit to contain a compose
file (`SAMPLE.entrypoint`). Everything sample-specific is in that file.

Host ports come from the run, never from the sample: the sample publishes
`${BENCH_HTTP_PORT:-<default>}` / `${BENCH_DB_PORT:-<default>}` and this
adapter exports both before every compose call, so two concurrent runs
cannot collide. Each run also gets its own compose project name.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import urlopen

import config
from src import log
from src import run as run_pkg
from src.errors import GateError
from src.run.process import ProcessRun, run_streamed
from src.run.sample_checkout import show_file

logger = log.get("stack")


class ComposeStack:
    def __init__(self, ctx: Any, options: dict[str, Any]):
        self.ctx = ctx
        self.options = options
        self.location = Path(ctx.sample_location)
        entrypoint = ctx.sample.get("entrypoint") or config.COMPOSE_FILE_NAME
        self.compose_file = self.location / entrypoint
        self.project = (config.COMPOSE_PROJECT_PREFIX + ctx.run_id)[:63]
        self.timeout_s = int(
            options.get("timeout_s", config.STACK_UP_TIMEOUT_S)
        )
        self._ports: dict[str, int] = {}
        self._file_env = config.load_env_file(
            self.location / config.SAMPLE_ENV_FILE
        )

    # --- process plumbing ----------------------------------------------------
    def _cmd(self, *args: str) -> list[str]:
        return [
            config.DOCKER,
            config.COMPOSE,
            "-p",
            self.project,
            "-f",
            str(self.compose_file),
            "--project-directory",
            str(self.location),
            *args,
        ]

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.update(self._file_env)
        if self._ports:
            env["BENCH_HTTP_PORT"] = str(self._ports["http"])
            env["BENCH_DB_PORT"] = str(self._ports["db"])
        return env

    def _cmd_for(self, compose_file: Path, *args: str) -> list[str]:
        return [
            config.DOCKER,
            config.COMPOSE,
            "-p",
            self.project,
            "-f",
            str(compose_file),
            "--project-directory",
            str(self.location),
            *args,
        ]

    def _run_cmd(
        self,
        cmd: list[str],
        stdin_text: str | None,
        check: bool,
        echo: bool,
    ) -> ProcessRun:
        """Run one compose call, live at `echo`'s level.

        A build is minutes of silence if its output is swallowed, so an
        echoed call prints as it happens; the quiet calls (`ps`, `config`,
        `exec`) stay at DEBUG to keep the operator's log readable. Every
        call is bounded by the stack timeout, so a wedged daemon cannot
        hang a gate forever.
        """
        logger.log(
            logging.INFO if echo else logging.DEBUG,
            "compose %s",
            " ".join(cmd[4:]),
        )
        run = run_streamed(
            cmd,
            cwd=self.location,
            env=self._env(),
            stdin_text=stdin_text,
            timeout_s=self.timeout_s,
            heartbeat_s=config.LOG_HEARTBEAT_S,
            logger=logger,
            sink=None,
            echo=echo,
        )
        if check and run.exit_code != 0:
            raise GateError(
                f"compose {' '.join(cmd[4:])} failed "
                f"({run.exit_code}) in {self.project}: "
                f"{(run.stderr or run.stdout).strip()[-2000:]}"
            )
        return run

    def _run(
        self,
        *args: str,
        stdin_text: str | None,
        check: bool,
        echo: bool,
    ) -> ProcessRun:
        return self._run_cmd(self._cmd(*args), stdin_text, check, echo)

    # --- lifecycle -----------------------------------------------------------
    def _allocate(self) -> None:
        if self._ports:
            return
        http_port, db_port = run_pkg.allocate_ports(2)
        self._ports = {"http": http_port, "db": db_port}

    def up(self) -> str:
        if not self.compose_file.is_file():
            raise GateError(
                f"sample {self.ctx.sample['slug']} declares entrypoint "
                f"'{self.compose_file.name}' but the pinned commit has no "
                "such file "
                f"({self.compose_file}). Add it to the sample and re-pin."
            )
        self._allocate()
        # `--build` is not optional: the sample's image IS its code, so a
        # gate that skipped the build would grade the pinned commit instead
        # of whatever the agent left in the worktree.
        logger.info(
            "starting %s (http port %s, db port %s)",
            self.project,
            self._ports["http"],
            self._ports["db"],
        )
        started = time.monotonic()
        self._run(
            "up",
            "-d",
            "--build",
            "--remove-orphans",
            stdin_text=None,
            check=True,
            echo=True,
        )
        self.await_ready()
        url = self.base_url()
        logger.info(
            "stack %s ready at %s (%.1fs)",
            self.project,
            url,
            time.monotonic() - started,
        )
        return url

    def down(self, volumes: bool = True) -> None:
        args = ["down", "--remove-orphans"]
        if volumes:
            args.insert(1, "-v")
        logger.info("stopping %s (volumes=%s)", self.project, volumes)
        self._run(*args, stdin_text=None, check=False, echo=True)

    def reset(self) -> str:
        self.down(volumes=True)
        return self.up()

    # --- readiness -----------------------------------------------------------
    # `compose up --wait` cannot be trusted: it exits 1 as soon as any service
    # exits, even with status 0 — and a sample legitimately uses a one-shot
    # service for one-off setup. Readiness is therefore *observed* rather than
    # asserted: every container must be up-and-not-unhealthy or exited
    # cleanly, and the published URL must answer.
    def await_ready(self) -> None:
        started = time.monotonic()
        deadline = started + self.timeout_s
        last_report = started
        while not self._settled():
            now = time.monotonic()
            if now >= deadline:
                raise GateError(
                    f"stack {self.project} did not become ready within "
                    f"{self.timeout_s}s: {self._summary()}"
                )
            if now - last_report >= config.LOG_HEARTBEAT_S:
                logger.info(
                    "waiting for %s (%ss): %s",
                    self.project,
                    int(now - started),
                    self._summary(),
                )
                last_report = now
            time.sleep(config.STACK_POLL_INTERVAL_S)

    @staticmethod
    def _settled_status(status: str) -> bool:
        """`compose ps` Status → has this container reached a final state?"""
        if status.startswith("Exited"):
            return status.startswith("Exited (0")
        if status.startswith("Up"):
            return (
                "(unhealthy)" not in status
                and "(health: starting)" not in status
            )
        return False

    def _settled(self) -> bool:
        rows = self._ps(include_stopped=True)
        if not rows:
            return False
        for row in rows:
            if not self._settled_status(row.get("Status") or ""):
                return False
        return self._answers()

    def _answers(self) -> bool:
        """Any HTTP answer proves the published port is serving."""
        try:
            with urlopen(
                self.base_url(), timeout=config.STACK_PROBE_TIMEOUT_S
            ) as response:
                return response.status < 500
        except HTTPError:
            # 4xx/5xx: the server is up and answering; content is not the
            # adapter's business.
            return True
        except (URLError, OSError):
            return False

    def _summary(self) -> str:
        rows = self._ps(include_stopped=True)
        if not rows:
            return "no containers"
        return "; ".join(
            f"{row.get('Service')}={row.get('Status')}" for row in rows
        )

    # --- introspection -------------------------------------------------------
    def base_url(self) -> str:
        http_port = self._ports.get("http")
        target = self.ctx.sample.get("target_url")
        if not target:
            target = (
                f"http://localhost:{http_port}"
                if http_port
                else "http://localhost:80"
            )
        if not http_port:
            return target
        parsed = urlparse(target)
        host = parsed.hostname or "localhost"
        return urlunparse(parsed._replace(netloc=f"{host}:{http_port}"))

    def ps(self) -> list[dict[str, Any]]:
        return self._ps(include_stopped=False)

    def _ps(self, include_stopped: bool) -> list[dict[str, Any]]:
        args = ["ps"]
        if include_stopped:
            args.append("--all")
        args += ["--format", "json"]
        out = self._run(
            *args, stdin_text=None, check=False, echo=False
        ).stdout.strip()
        if not out:
            return []
        try:
            parsed = json.loads(out)
            return parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            return [
                json.loads(line) for line in out.splitlines() if line.strip()
            ]

    def declared_pinned(self) -> dict[str, Any]:
        # The contract is the PINNED compose file, never the worktree one:
        # an agent that adds a network or a published port must not thereby
        # widen the allowance it is graded against. The blob is written
        # under the run directory so the rendered contract is auditable.
        self._allocate()
        commit_sha = self.ctx.sample["commit_sha"]
        blob = show_file(self.location, commit_sha, self.compose_file.name)
        rendered = self.ctx.paths.root / f"pinned-{self.compose_file.name}"
        rendered.write_text(blob)
        return self._render(rendered)

    def declared(self) -> dict[str, Any]:
        # The submission: the worktree file, rendered with the same run
        # ports as the contract so the two are comparable.
        self._allocate()
        return self._render(self.compose_file)

    def _render(self, compose_file: Path) -> dict[str, Any]:
        # Offline: `config` resolves substitution, override files,
        # `external:` and `name:` without a docker daemon.
        out = self._run_cmd(
            self._cmd_for(compose_file, "config", "--format", "json"),
            stdin_text=None,
            check=True,
            echo=False,
        ).stdout
        return json.loads(out)

    def exec_(
        self, service: str, argv: list[str], stdin: str | None = None
    ) -> str:
        return self._run(
            "exec",
            "-T",
            service,
            *argv,
            stdin_text=stdin,
            check=True,
            echo=False,
        ).stdout
