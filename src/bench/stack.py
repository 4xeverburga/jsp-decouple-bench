"""The scoring stack, driven from the host.

Scoring has no Inspect sandbox. The scorer is a host process — Playwright
drives the app, the database and the traces are read back — so the app's
stack is a plain `docker compose` project it starts and removes itself.
Nothing here runs inside a container, which is why the bench can itself run
anywhere a `docker` CLI reaches a daemon.

One stack per case: the goldens were captured on a pristine database.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Timer

import settings

from .compose import sample_env, scoring_compose


def _say(line: str) -> None:
    print(f"[stack] {line.rstrip()}", file=sys.stderr, flush=True)


class Stack:
    def __init__(self, slug: str) -> None:
        prefix = settings.STACK_PROJECT_PREFIX
        self.project = f"{prefix}{slug}-{uuid.uuid4().hex[:8]}"
        self._compose = scoring_compose(slug)
        self._env = {
            **os.environ,
            "BENCH_CHECKOUT": settings.checkout(),
            "BENCH_SAMPLE_ENV": str(sample_env(slug)),
        }

    def _argv(self, *args: str) -> list[str]:
        return [
            "docker",
            "compose",
            "--ansi",
            "never",
            "-p",
            self.project,
            "-f",
            str(self._compose),
            *args,
        ]

    def _stream(self, args: tuple[str, ...], timeout: int) -> None:
        """Run, echoing every line as it arrives: a build is minutes long."""
        process = subprocess.Popen(
            self._argv(*args),
            env=self._env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        timer = Timer(timeout, process.kill)
        timer.start()
        try:
            assert process.stdout is not None
            for line in process.stdout:
                _say(line)
            if process.wait() != 0:
                raise RuntimeError(f"docker compose {args[0]} failed")
        finally:
            timer.cancel()
            process.kill()

    def up(self) -> None:
        self._stream(("up", "-d", "--build"), settings.STACK_BUILD_TIMEOUT_S)
        self._await_ready()

    def _states(self) -> list[dict]:
        out = subprocess.run(
            self._argv("ps", "-a", "--format", "json"),
            env=self._env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if out.startswith("["):
            return json.loads(out)
        return [json.loads(line) for line in out.splitlines()]

    def _await_ready(self) -> None:
        """Wait until every service is healthy or a one-shot exited 0.

        `up --wait` is no use here: it fails when a one-shot service exits,
        even successfully, and the stacks have one.
        """
        deadline = time.monotonic() + settings.STACK_HEALTHY_TIMEOUT_S
        last = 0.0
        while time.monotonic() < deadline:
            waiting = []
            for svc in self._states():
                name, state = svc["Service"], svc["State"]
                if state == "exited":
                    if svc["ExitCode"] != 0:
                        raise RuntimeError(f"{name} exited {svc['ExitCode']}")
                elif state != "running" or svc["Health"] not in (
                    "",
                    "healthy",
                ):
                    waiting.append(f"{name}={svc['Health'] or state}")
            if not waiting:
                return
            if time.monotonic() - last > settings.STACK_REPORT_INTERVAL_S:
                _say(f"waiting for {', '.join(waiting)}")
                last = time.monotonic()
            time.sleep(settings.STACK_POLL_INTERVAL_S)
        raise RuntimeError(
            f"stack not ready after {settings.STACK_HEALTHY_TIMEOUT_S}s"
        )

    def down(self) -> None:
        subprocess.run(
            self._argv("down", "-v", "--remove-orphans", "--rmi", "local"),
            env=self._env,
            capture_output=True,
        )

    def copy_out(self, service: str, source: str, target: Path) -> bool:
        """Take a file out of a running service; False if it is not there.

        Best effort on purpose: a case is graded on its behaviour, so a
        missing file must not turn a measurement into an error.
        """
        result = subprocess.run(
            self._argv("cp", f"{service}:{source}", str(target)),
            env=self._env,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    async def exec(
        self, service: str, argv: list[str], stdin: str
    ) -> subprocess.CompletedProcess:
        return await asyncio.to_thread(
            subprocess.run,
            self._argv("exec", "-T", service, *argv),
            env=self._env,
            input=stdin,
            capture_output=True,
            text=True,
        )


@asynccontextmanager
async def running(slug: str):
    """The case's stack, built from the tree under test, removed after."""
    stack = Stack(slug)
    try:
        await asyncio.to_thread(stack.up)
        yield stack
    finally:
        stack.down()
