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


# --- storage. Relative to the repository root; never a per-run choice. -----
SEEDS = ROOT / "seeds"
SAMPLES = ROOT / "src" / "samples"
OUT = ROOT / "out"
EVIDENCE = OUT / "evidence"
SOLVES = OUT / "solves"
WORKSPACES = OUT / "workspaces"
LOGS = OUT / "evals"

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

# --- the agent, and the model that answers its bridged calls. -------------
OPENCODE_MODEL = _text("OPENCODE_MODEL")
OPENCODE_VERSION = _text("OPENCODE_VERSION")

# --- the model that answers, and the credential its provider reads. -------
# Inspect's `openai-api` provider takes both from the process environment,
# and derives their names from the service segment of the model string
# (`openai-api/<service>/<model>` reads `<SERVICE>_API_KEY` and
# `<SERVICE>_BASE_URL`), so these are the variable names themselves, passed
# through to the eval untouched.
ANSWER_MODEL = _text("BENCH_ANSWER_MODEL")
MODEL_ENV = {
    "OPENCODE_GO_API_KEY": _text("OPENCODE_GO_API_KEY"),
    "OPENCODE_GO_BASE_URL": _text("OPENCODE_GO_BASE_URL"),
}

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
