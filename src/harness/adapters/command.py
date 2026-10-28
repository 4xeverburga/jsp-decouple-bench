"""src/harness/adapters/command.py — the only harness: drive any agent CLI.

The prompt goes in on **stdin**, exactly as a user would hand it over.
Nothing about the run is put in the environment: an agent that prints its
env must not discover that it is being measured. A copy of the prompt is
kept at `<run>/harness-prompt.md` for the supervisor's audit trail, but no
such path is handed to the agent.

Which CLI, which model and which effort run is **the command itself**, the
one every run carries in `--harness-cmd`, so no agent ever needs a class
here. `name` is only the label the run is recorded under.

The command runs with cwd = the sample checkout and edits it in place. The
diff is read back afterwards from git, never from the harness's own claims.
"""

from __future__ import annotations

import os
from pathlib import Path

import config
from src import log
from src.errors import BenchError
from src.harness.ports import HarnessResult, HarnessTask
from src.run.process import run_streamed

logger = log.get("harness")


class CommandHarness:
    """One command line, run as `bash -lc <cmd>` with the prompt on stdin."""

    def __init__(self, name: str, cmd: str):
        if not cmd:
            raise BenchError(
                "no agent command: pass --harness-cmd '...'. The prompt "
                "arrives on stdin, so a CLI that takes it as an argument "
                'reads it with "$(cat)".'
            )
        self.name = name
        self.cmd = cmd
        self.timeout_s = config.HARNESS_TIMEOUT_S

    @staticmethod
    def _clean_env() -> dict[str, str]:
        """Never hand the agent a variable that names the bench.

        The supervisor's shell may well have `BENCH_*` exported; inheriting it
        would tell an agent that runs `env` exactly what is going on.
        """
        return {
            k: v
            for k, v in os.environ.items()
            if not k.upper().startswith("BENCH_")
        }

    def run(self, task: HarnessTask, log_dir: Path) -> HarnessResult:
        log_dir = Path(log_dir)
        prompt = task.render()
        (log_dir / "harness-prompt.md").write_text(prompt)
        log_file = log_dir / "harness.log"

        logger.info("harness %r: %s", self.name, self.cmd)
        logger.info("cwd %s (timeout %ss)", task.cwd, self.timeout_s)
        with log_file.open("w", encoding="utf-8") as sink:
            # The agent's own words, live: this is the only evidence that a
            # 30-minute session is working rather than wedged.
            sink.write(
                f"$ {self.cmd}\ncwd: {task.cwd}\n"
                "# stdout and stderr, interleaved as produced\n\n"
            )
            sink.flush()
            run = run_streamed(
                ["bash", "-lc", self.cmd],
                cwd=task.cwd,
                env=self._clean_env(),
                stdin_text=prompt,
                timeout_s=self.timeout_s,
                heartbeat_s=config.LOG_HEARTBEAT_S,
                logger=logger,
                sink=sink,
                echo=True,
            )
            sink.write(f"\nexit: {run.exit_code} ({run.duration_s:.1f}s)\n")
        if run.exit_code == 0:
            logger.info(
                "harness %r exited 0 in %.1fs (log %s)",
                self.name,
                run.duration_s,
                log_file,
            )
        else:
            logger.error(
                "harness %r exited %s%s in %.1fs (log %s)",
                self.name,
                run.exit_code,
                " after timeout" if run.timed_out else "",
                run.duration_s,
                log_file,
            )
        return HarnessResult(
            exit_code=run.exit_code,
            duration_s=run.duration_s,
            command=self.cmd,
            log_path=log_file,
        )
