"""The bench's whole configuration, in one place, read from `.env`.

Two kinds of value live here, and only one of them is a parameter:

- **Parameters**, from `.env` at the repository root — the browser, the
  viewport, the locale, the clock, the timeouts, the model names. They are
  required: there are no defaults, so a missing key is a configuration
  error, not a silent fallback. The shell environment is not consulted for
  them; `.env` is the single source of truth.
- **Run inputs**, from the process environment — the checkout under test,
  the URL its stack publishes, the sample's own env folder. They change
  from run to run and are set by the driver (`src/bench/cli.py`), so they
  cannot live in a file.

Copy the template once: `cp .env.example .env`. `.env` is untracked.
"""

import os
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"

_ENV = dotenv_values(ENV_FILE)


def _text(name: str) -> str:
    """A required parameter. An absent key is an error, not a default."""
    value = _ENV.get(name)
    if value is None or value == "":
        raise KeyError(
            f"{name} is missing from {ENV_FILE}: copy .env.example to .env "
            f"and fill it in"
        )
    return value


def _integer(name: str) -> int:
    return int(_text(name))


def _flag(name: str) -> bool:
    return _text(name) == "1"


def _names(name: str) -> list[str]:
    """A required list of variable names, possibly empty.

    Absent is an error like any other key, but an empty value is a real
    answer: a mock or local model needs no credential at all.
    """
    value = _ENV.get(name)
    if value is None:
        raise KeyError(
            f"{name} is missing from {ENV_FILE}: copy .env.example to .env "
            f"and fill it in (empty is allowed, absent is not)"
        )
    return value.split()


# --- storage. Relative to the repository root; never a per-run choice. -----
SEEDS = ROOT / "seeds"
SAMPLES = ROOT / "src" / "samples"
OUT = ROOT / "out"
EVIDENCE = OUT / "evidence"
SOLVES = OUT / "solves"
WORKSPACES = OUT / "workspaces"
LOGS = OUT / "evals"

# --- the solve workspace, as the sandbox sees it. -------------------------
# Every sample's `env/solve.yaml` mounts the checkout here and the agent
# starts here. It is deliberately not the host path: that one spells this
# repository's name, and a `pwd` is enough to send an agent looking for it.
# One name for every sample, so a new toolbox inherits it.
SOLVE_ROOT = "/workspace"

# --- determinism. The goldens were captured with these; not a preference. --
LOCALE = _text("BENCH_LOCALE")
TIMEZONE_ID = _text("BENCH_TIMEZONE_ID")
VIEWPORT_WIDTH = _integer("BENCH_VIEWPORT_WIDTH")
VIEWPORT_HEIGHT = _integer("BENCH_VIEWPORT_HEIGHT")
CASE_TIMEOUT_MS = _integer("BENCH_CASE_TIMEOUT_MS")

# --- the browser a case is played in. Chromium is the only engine the
# goldens were captured with, so it is not a knob; headless is. -------------
HEADLESS = _flag("BENCH_HEADLESS")

# --- the stack a case is scored on. ----------------------------------------
STACK_BUILD_TIMEOUT_S = _integer("STACK_BUILD_TIMEOUT_S")
STACK_HEALTHY_TIMEOUT_S = _integer("STACK_HEALTHY_TIMEOUT_S")
STACK_POLL_INTERVAL_S = _integer("STACK_POLL_INTERVAL_S")
STACK_REPORT_INTERVAL_S = _integer("STACK_REPORT_INTERVAL_S")
STACK_PROJECT_PREFIX = _text("STACK_PROJECT_PREFIX")

# --- the agent the solve phase runs. Three values that describe ONE
# agent, so switching AGENT means taking its version and its wire model
# along: `src/bench/agents.py` is what each name means. -------------------
AGENT = _text("AGENT")
# The wire name: the string the CLI formats its requests for. It must be
# one its own catalogue knows (this is what refuses a name before any
# request is made), and it is NOT the model that answers.
AGENT_MODEL = _text("AGENT_MODEL")
AGENT_VERSION = _text("AGENT_VERSION")

# --- the model that answers, and the variables its provider reads. --------
# WHICH variables those are is `.env`'s business (`BENCH_MODEL_ENV`), not
# this file's: a provider reads its credential from the process environment
# under a name of its own — one `*_API_KEY` for Inspect's native providers,
# `<SERVICE>_API_KEY` + `<SERVICE>_BASE_URL` for an OpenAI-compatible
# gateway — so they are passed through untouched. A new answerer is two
# lines in `.env` and nothing here. They follow the ANSWERER, not the agent:
# the agent's own sandbox gets a dummy credential and the bridge answers.
ANSWER_MODEL = _text("BENCH_ANSWER_MODEL")
MODEL_ENV = {name: _text(name) for name in _names("BENCH_MODEL_ENV")}

# --- the model the score phase is labelled with. It answers nothing, but
# Inspect requires one; `mockllm/model` makes that explicit in the log. ----
SCORE_MODEL = _text("BENCH_SCORE_MODEL")


def checkout() -> str:
    """The tree under test: what the agent edited, or what it left behind."""
    return os.environ["BENCH_CHECKOUT"]


def base_url() -> str:
    """Where the running stack publishes the app, for this run only."""
    return os.environ["BENCH_BASE_URL"]


# Case flows do `import settings`, so the repository root must be importable
# from every entry point — including a scorer running on a worker thread.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
