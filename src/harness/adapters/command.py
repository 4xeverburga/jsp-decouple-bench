"""src/harness/adapters/command.py — `command` harness: drive any agent CLI.

The prompt goes in on **stdin**, exactly as a user would hand it over.
Nothing about the run is put in the environment: an agent that prints its
env must not discover that it is being measured. A copy of the prompt is
kept at `<run>/harness-prompt.md` for the supervisor's audit trail, but no
such path is handed to the agent.

The command runs with cwd = the sample checkout and edits it in place. The
diff is read back afterwards from git, never from the harness's own claims.

Options (CLI `--harness-cmd` wins over `BENCH_HARNESS_CMD`):
    cmd        shell command to run (required)
    timeout_s  default HARNESS_TIMEOUT_S
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any

import config
from src.errors import BenchError
from src.harness.ports import HarnessResult, HarnessTask


class CommandHarness:
    name = "command"

    def __init__(self, options: dict[str, Any] | None = None):
        self.options = options or {}
        self.cmd = self.options.get("cmd") or config.HARNESS_CMD
        if not self.cmd:
            raise BenchError(
                f"harness '{self.name}' needs a command: pass --harness-cmd "
                f"or set BENCH_HARNESS_CMD"
            )
        self.timeout_s = int(self.options.get("timeout_s", config.HARNESS_TIMEOUT_S))

    @staticmethod
    def _clean_env() -> dict[str, str]:
        """Never hand the agent a variable that names the bench.

        The supervisor's shell may well have `BENCH_*` exported; inheriting it
        would tell an agent that runs `env` exactly what is going on.
        """
        return {k: v for k, v in os.environ.items()
                if not k.upper().startswith("BENCH_")}

    def run(self, task: HarnessTask, log_dir: Path) -> HarnessResult:
        log_dir = Path(log_dir)
        prompt = task.render()
        (log_dir / "harness-prompt.md").write_text(prompt)
        log = log_dir / "harness.log"

        started = time.monotonic()
        try:
            proc = subprocess.run(
                ["bash", "-lc", self.cmd],
                cwd=str(task.cwd), input=prompt, text=True, capture_output=True,
                env=self._clean_env(), timeout=self.timeout_s,
            )
            exit_code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = f"harness timed out after {self.timeout_s}s\n"

        duration = time.monotonic() - started
        log.write_text(
            f"$ {self.cmd}\ncwd: {task.cwd}\nexit: {exit_code} "
            f"({duration:.1f}s)\n\n--- stdout ---\n{stdout}\n"
            f"--- stderr ---\n{stderr}"
        )
        return HarnessResult(exit_code=exit_code, duration_s=duration, log_path=log)
