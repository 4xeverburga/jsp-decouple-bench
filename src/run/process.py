"""src/run/process.py — run a child process and watch it happen.

`subprocess.run(capture_output=True)` says nothing until the child exits,
which is indistinguishable from a hang: a compose build or a 30-minute
agent session would print nothing at all. This streams the child's output
line by line into the operator's log (and, when asked, into a file the run
keeps) as it is produced.

It also owns termination: on timeout, on Ctrl-C or on any exception the
child's whole **process group** is killed, so a harness can never leave an
agent (or a container tool) running behind a dead supervisor.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO

# After SIGTERM, how long the group may take to die before SIGKILL.
KILL_GRACE_S = 10

# `timeout(1)`'s convention for "killed because it ran too long".
TIMEOUT_EXIT = 124


@dataclass(frozen=True)
class ProcessRun:
    exit_code: int
    duration_s: float
    stdout: str
    stderr: str
    timed_out: bool


def _pump(
    stream: IO[str],
    sink: IO[str] | None,
    logger: logging.Logger,
    level: int,
    captured: list[str],
) -> None:
    """Drain one pipe: keep every line and mirror it, never block the child.

    Blank lines are kept in the file (they carry a build's formatting) but
    not logged, so a heartbeat never buries a real message.
    """
    for line in stream:
        captured.append(line)
        if sink is not None:
            sink.write(line)
            sink.flush()
        if line.strip():
            logger.log(level, line.rstrip("\n"))


def _terminate(proc: subprocess.Popen) -> None:
    """Kill the child's process group: politely first, then not.

    The group is what matters: the harness runs `bash -lc '<agent>'`, so
    killing bash alone would orphan the agent it spawned.
    """
    try:
        group = os.getpgid(proc.pid)
    except (ProcessLookupError, OSError):
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(group, sig)
        except (ProcessLookupError, OSError):
            return
        try:
            proc.wait(timeout=KILL_GRACE_S)
            return
        except subprocess.TimeoutExpired:
            continue


def _feed(proc: subprocess.Popen, text: str) -> None:
    """Hand the child its stdin, then close it so `$(cat)` sees EOF."""
    if proc.stdin is None:  # pragma: no cover - we always open the pipe
        return
    try:
        proc.stdin.write(text)
        proc.stdin.close()
    except (BrokenPipeError, ValueError):
        # The child exited without reading. Its exit status says why; a
        # traceback here would only hide that.
        pass


def _wait(
    proc: subprocess.Popen,
    started: float,
    timeout_s: int,
    heartbeat_s: int,
    logger: logging.Logger,
) -> tuple[int, bool]:
    """Wait for exit, proving liveness every `heartbeat_s` seconds."""
    deadline = started + timeout_s
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            logger.error("timed out after %ss — killing the group", timeout_s)
            _terminate(proc)
            return TIMEOUT_EXIT, True
        try:
            return proc.wait(timeout=min(heartbeat_s, remaining)), False
        except subprocess.TimeoutExpired:
            elapsed = int(time.monotonic() - started)
            logger.info("still running (%ss elapsed)", elapsed)


def run_streamed(
    cmd: list[str],
    cwd: Path,
    env: dict[str, str],
    stdin_text: str | None,
    timeout_s: int,
    heartbeat_s: int,
    logger: logging.Logger,
    sink: IO[str] | None,
    echo: bool,
) -> ProcessRun:
    """Run `cmd` to completion, mirroring its output while it runs.

    `echo` picks INFO for a step the operator is waiting on (a build, an
    agent) and DEBUG for quiet introspection calls that would otherwise
    flood the log.
    """
    level = logging.INFO if echo else logging.DEBUG
    started = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdin=(
            subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        start_new_session=True,
    )
    out: list[str] = []
    err: list[str] = []
    pumps = [
        threading.Thread(
            target=_pump,
            args=(proc.stdout, sink, logger, level, out),
            daemon=True,
        ),
        threading.Thread(
            target=_pump,
            args=(proc.stderr, sink, logger, level, err),
            daemon=True,
        ),
    ]
    for pump in pumps:
        pump.start()
    try:
        if stdin_text is not None:
            _feed(proc, stdin_text)
        exit_code, timed_out = _wait(
            proc, started, timeout_s, heartbeat_s, logger
        )
    finally:
        if proc.poll() is None:  # Ctrl-C, or an unexpected error
            logger.warning("interrupted — killing the group")
            _terminate(proc)
        for pump in pumps:
            pump.join()
    return ProcessRun(
        exit_code=exit_code,
        duration_s=time.monotonic() - started,
        stdout="".join(out),
        stderr="".join(err),
        timed_out=timed_out,
    )
