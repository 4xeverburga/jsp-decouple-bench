"""The bench's whole configuration, in one place, read from `.env`.

Two kinds of value live here, and only one of them is a parameter:

- **Parameters**, from `.env` at the repository root — the browser, the
  viewport, the locale, the clock, the timeouts, the model names. They are
  required: there are no defaults, so a missing key is a configuration
  error, not a silent fallback. The shell environment is not consulted for
  them; `.env` is the single source of truth. `.env` also holds the
  credentials a run profile names, and nothing about the run itself.
- **Run profiles**, from `runs.yaml` — who solves a manifest, with which
  model and effort. Named, tracked, chosen per invocation with
  `--profile`; see `profile`.
- **Run inputs**, from the process environment — the checkout under test,
  the URL its stack publishes, the sample's own env folder. They change
  from run to run and are set by the driver (`src/bench/cli.py`), so they
  cannot live in a file.

Copy the template once: `cp .env.example .env`. `.env` is untracked.
"""

import os
import sys
from pathlib import Path

import yaml
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
TRACES = OUT / "traces"
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

# --- the spans a case produces, kept before its stack is removed. ---------
# Every sample's stack names its collector `collector` and has it write
# this file (`prepare-repo-for-dataset`); a sample that does otherwise is
# prepared wrong, so neither is a per-run knob. The wait is the batch
# exporter's flush: spans arrive a few seconds after the request that made
# them, and `down -v` deletes the volume just after.
STACK_TRACES_SERVICE = "collector"
STACK_TRACES_FILE = "/traces/traces.jsonl"
TRACE_FLUSH_WAIT_S = 8

# --- who solves a run: a named profile in `runs.yaml`, never `.env`. -----
# A profile is a choice, not a secret, so it is tracked; `.env` only holds
# the credentials a profile's `model_env` names. `src/agents/` defines the
# agents a profile can name.
RUNS_FILE = ROOT / "runs.yaml"
PROFILE_KEYS = (
    "agent",
    "agent_model",
    "agent_version",
    "answer_model",
    "model_env",
    "reasoning_effort",
    "model_args",
)
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")


def profile(name: str) -> dict:
    """The run profile called ``name``, exactly as `runs.yaml` spells it.

    Every key is required and no other is allowed, so a typo is an error
    and not a value that silently never applies. Credentials are not part
    of it: `credentials` resolves `model_env` against `.env`.
    """
    profiles = yaml.safe_load(RUNS_FILE.read_text())
    if name not in profiles:
        raise KeyError(
            f"no profile {name!r} in {RUNS_FILE}; it has: "
            f"{', '.join(sorted(profiles))}"
        )
    chosen = profiles[name]
    missing = [key for key in PROFILE_KEYS if key not in chosen]
    unknown = sorted(set(chosen) - set(PROFILE_KEYS))
    if missing or unknown:
        raise KeyError(
            f"profile {name!r} in {RUNS_FILE}: missing {missing}, "
            f"unknown {unknown}"
        )
    if chosen["reasoning_effort"] not in EFFORTS:
        raise ValueError(
            f"profile {name!r}: reasoning_effort must be one of {EFFORTS}"
        )
    return {key: chosen[key] for key in PROFILE_KEYS}


def credentials(chosen: dict) -> dict[str, str]:
    """The values of the variables a profile's provider reads, from `.env`.

    WHICH variables is the profile's business: a provider reads its
    credential under a name of its own — one `*_API_KEY` for Inspect's
    native providers, `<SERVICE>_API_KEY` + `<SERVICE>_BASE_URL` for an
    OpenAI-compatible gateway. A CLI agent's sandbox never sees them: it
    gets a dummy credential and the bridge answers.
    """
    return {name: _text(name) for name in chosen["model_env"]}


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
