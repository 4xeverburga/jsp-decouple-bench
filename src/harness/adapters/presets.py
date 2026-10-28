"""src/harness/adapters/presets.py — named agent CLIs.

Each preset is `command` with a conventional invocation. The prompt arrives
on stdin; a CLI that wants an argument reads it with `"$(cat)"`. If your
build of a tool differs, override with `--harness-cmd '...'` — the preset
then only supplies the name.
"""
from __future__ import annotations

from typing import Any

import config
from src.harness.adapters.command import CommandHarness


class _Preset(CommandHarness):
    def __init__(self, options: dict[str, Any] | None = None):
        options = dict(options or {})
        if not options.get("cmd"):
            options["cmd"] = config.HARNESS_CMD or config.PRESET_CMDS[self.name]
        super().__init__(options)


class ClaudeCodeHarness(_Preset):
    """`claude -p`: print mode, prompt on stdin."""
    name = "claude-code"


class OpenCodeHarness(_Preset):
    """`opencode run <message>`: the message is an argument."""
    name = "opencode"


class PiHarness(_Preset):
    """`pi`: prompt on stdin."""
    name = "pi"
