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
import os
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import config
from src import run as run_pkg
from src.errors import GateError


class ComposeStack:
    def __init__(self, ctx: Any, options: dict[str, Any]):
        self.ctx = ctx
        self.options = options
        self.location = Path(ctx.sample_location)
        entrypoint = ctx.sample.get("entrypoint") or config.COMPOSE_FILE_NAME
        self.compose_file = self.location / entrypoint
        self.project = (config.COMPOSE_PROJECT_PREFIX + ctx.run_id)[:63]
        self.timeout_s = int(options.get("timeout_s", config.STACK_UP_TIMEOUT_S))
        self._ports: dict[str, int] = {}
        self._file_env = config.load_env_file(self.location / config.SAMPLE_ENV_FILE)

    # --- process plumbing ----------------------------------------------------
    def _cmd(self, *args: str) -> list[str]:
        return [
            config.DOCKER, config.COMPOSE,
            "-p", self.project,
            "-f", str(self.compose_file),
            "--project-directory", str(self.location),
            *args,
        ]

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.update(self._file_env)
        if self._ports:
            env["BENCH_HTTP_PORT"] = str(self._ports["http"])
            env["BENCH_DB_PORT"] = str(self._ports["db"])
        return env

    def _run(self, *args: str, stdin: str | None = None,
             check: bool = True) -> subprocess.CompletedProcess:
        proc = subprocess.run(
            self._cmd(*args), cwd=str(self.location), env=self._env(),
            input=stdin, capture_output=True, text=True,
        )
        if check and proc.returncode != 0:
            raise GateError(
                f"compose {' '.join(args)} failed ({proc.returncode}) in "
                f"{self.project}: {(proc.stderr or proc.stdout).strip()[-2000:]}"
            )
        return proc

    def _docker(self, *args: str) -> str:
        proc = subprocess.run(
            [config.DOCKER, *args], capture_output=True, text=True
        )
        if proc.returncode != 0:
            raise GateError(f"docker {' '.join(args)} failed: {proc.stderr.strip()}")
        return proc.stdout

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
                f"'{self.compose_file.name}' but the pinned commit has no such file "
                f"({self.compose_file}). Add it to the sample and re-pin."
            )
        self._allocate()
        self._run(
            "up", "-d", "--wait", "--wait-timeout", str(self.timeout_s),
            "--remove-orphans",
        )
        return self.base_url()

    def down(self, volumes: bool = True) -> None:
        args = ["down", "--remove-orphans"]
        if volumes:
            args.insert(1, "-v")
        self._run(*args, check=False)

    def reset(self) -> str:
        self.down(volumes=True)
        return self.up()

    # --- introspection -------------------------------------------------------
    def base_url(self) -> str:
        http_port = self._ports.get("http")
        target = self.ctx.sample.get("target_url")
        if not target:
            target = f"http://localhost:{http_port}" if http_port else "http://localhost:80"
        if not http_port:
            return target
        parsed = urlparse(target)
        host = parsed.hostname or "localhost"
        return urlunparse(parsed._replace(netloc=f"{host}:{http_port}"))

    def ps(self) -> list[dict[str, Any]]:
        out = self._run("ps", "--format", "json", check=False).stdout.strip()
        if not out:
            return []
        try:
            parsed = json.loads(out)
            return parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            return [json.loads(line) for line in out.splitlines() if line.strip()]

    def inspect(self) -> list[dict[str, Any]]:
        ids = [row["ID"] for row in self.ps() if row.get("ID")]
        if not ids:
            return []
        return json.loads(self._docker("inspect", *ids))

    def declared(self) -> dict[str, Any]:
        out = self._run("config", "--format", "json").stdout
        return json.loads(out)

    def exec_(self, service: str, argv: list[str], stdin: str | None = None) -> str:
        return self._run("exec", "-T", service, *argv, stdin=stdin).stdout
