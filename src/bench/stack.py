"""The scoring stack, driven from the host.

Scoring has no Inspect sandbox. The scorer is a host process — Playwright
drives the app, the database and the traces are read back — so the app's
stack is a plain `docker compose` project it starts and removes itself.
Nothing here runs inside a container, which is why the bench can itself run
anywhere a `docker` CLI reaches a daemon.

One stack per case: the goldens were captured on a pristine database.

Stacks of the same sample can run side by side. Each is its own compose
project and publishes on a free host port it picks itself, so the URL a
case is played against belongs to the stack (`Stack.base_url`), not to the
process. The goldens do not care which port it was: parity replaces the
base URL with a token and the span condenser erases hosts.
"""

import asyncio
import fcntl
import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Timer
from typing import IO
from urllib.parse import urlsplit, urlunsplit

import settings

from .compose import sample_env, scoring_compose
from .seeds import sample

# What `docker compose up` prints when the host port went to someone else
# between the pick and the bind.
PORT_TAKEN = re.compile(r"port is already allocated|address already in use")


def _say(line: str) -> None:
    print(f"[stack] {line.rstrip()}", file=sys.stderr, flush=True)


class PortTakenError(RuntimeError):
    """`up` lost the port it picked: pick another, it is not a broken app."""


def _free_port() -> int:
    """A host port nothing listens on right now, chosen by the kernel.

    Bound on every interface, as compose publishes, so a port that is only
    free on loopback is not mistaken for a free one.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("", 0))
        return probe.getsockname()[1]


def _at_port(url: str, port: int) -> str:
    """The sample's `target_url`, context path and all, on ``port``."""
    parts = urlsplit(url)
    return urlunsplit(parts._replace(netloc=f"{parts.hostname}:{port}"))


class Stack:
    def __init__(self, slug: str) -> None:
        prefix = settings.STACK_PROJECT_PREFIX
        self.project = f"{prefix}{slug}-{uuid.uuid4().hex[:8]}"
        self._compose = scoring_compose(slug)
        self._target = sample(slug)["target_url"]
        self._env = {
            **os.environ,
            "BENCH_CHECKOUT": settings.checkout(),
            "BENCH_SAMPLE_ENV": str(sample_env(slug)),
        }
        self.base_url = ""

    def _publish(self, port: int) -> None:
        """Bind the app to ``port``: compose and the flows both follow it.

        `APP_HTTP_PORT` is what the sample's compose publishes and what its
        public-URL variable defaults to, so the app's own links and the
        address the flows drive cannot disagree.
        """
        self._env["APP_HTTP_PORT"] = str(port)
        self.base_url = _at_port(self._target, port)

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
        taken = False
        try:
            assert process.stdout is not None
            for line in process.stdout:
                _say(line)
                taken = taken or PORT_TAKEN.search(line) is not None
            if process.wait() != 0:
                if taken:
                    raise PortTakenError(f"compose {args[0]}: port taken")
                raise RuntimeError(f"docker compose {args[0]} failed")
        finally:
            timer.cancel()
            process.kill()

    def up(self) -> None:
        """Build and start on a free port; on a lost port, start again.

        A retry removes what the failed `up` created, volumes included, so
        the stack that finally answers still has a pristine database. The
        built image is kept: only the first attempt pays for the build.
        """
        for _ in range(settings.STACK_PORT_ATTEMPTS):
            self._publish(_free_port())
            try:
                self._stream(
                    ("up", "-d", "--build"), settings.STACK_BUILD_TIMEOUT_S
                )
            except PortTakenError:
                _say(f"port of {self.base_url} was taken; picking another")
                self._remove(("down", "-v", "--remove-orphans"))
                continue
            _say(f"{self.project} publishes {self.base_url}")
            self._await_ready()
            return
        raise RuntimeError(
            f"{self.project}: no free port after "
            f"{settings.STACK_PORT_ATTEMPTS} attempts"
        )

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

    def _remove(self, args: tuple[str, ...]) -> None:
        subprocess.run(
            self._argv(*args),
            env=self._env,
            capture_output=True,
        )

    def down(self) -> None:
        self._remove(("down", "-v", "--remove-orphans", "--rmi", "local"))

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


def _try_slot() -> IO | None:
    """One of the host's stack slots, held until closed; None if all taken.

    A slot is an exclusive `flock` on its own file, so it is shared by
    every bench process on the host and freed by the kernel when the
    process that held it dies, whatever killed it.
    """
    settings.LOCKS.mkdir(parents=True, exist_ok=True)
    for index in range(settings.STACK_MAX_LIVE):
        handle = open(settings.LOCKS / f"stack-{index}.lock", "w")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            continue
        return handle
    return None


async def _slot() -> IO:
    """Wait for a free stack slot, polling, so a time limit can cancel it."""
    reported = False
    while True:
        handle = _try_slot()
        if handle is not None:
            return handle
        if not reported:
            _say(
                f"all {settings.STACK_MAX_LIVE} stack slots are taken; "
                f"waiting for one"
            )
            reported = True
        await asyncio.sleep(settings.STACK_POLL_INTERVAL_S)


@asynccontextmanager
async def running(slug: str):
    """The case's stack, built from the tree under test, removed after."""
    slot = await _slot()
    try:
        stack = Stack(slug)
        try:
            await asyncio.to_thread(stack.up)
            yield stack
        finally:
            stack.down()
    finally:
        slot.close()
