"""The bench's whole configuration, in one place, read from `.env`.

Two kinds of value live here, and only one of them is a parameter:

- **Parameters**, from `.env` at the repository root — the browser, the
  viewport, the locale, the clock, the timeouts, the model names. They are
  required: there are no defaults, so a missing key is a configuration
  error, not a silent fallback. The shell environment is not consulted for
  them; `.env` is the single source of truth. `.env` also holds the
  credentials a profile names, and nothing about the run itself.
- **Profiles**, from `tasks-config.yaml` — who solves a manifest, with
  which model and effort (`solve_profiles`, chosen with `--profile`), and
  which model judges its spans (`score_profiles`, chosen with
  `--score-profile`). Named, tracked, chosen per invocation; see
  `solve_profile` and `score_profile`.
- **Run inputs**, from the process environment — the checkout under test
  and the sample's own env folder. They change from run to run and are set
  by the driver (`src/bench/cli.py`), so they cannot live in a file. The
  address a stack publishes is not one: every stack picks a free host port
  of its own and carries the URL it answers on (`stack.Stack.base_url`).

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
LOGS = OUT / "evals"
GIT_AUTHOR_EMAIL = _text("GIT_AUTHOR_EMAIL")
# One lock file per stack slot: how many stacks this host runs at once,
# across every bench process on it (`stack.running`).
LOCKS = OUT / "locks"

# --- the solve workspace, as the sandbox sees it. -------------------------
# Every sample's `env/solve.yaml` mounts the checkout here and the agent
# starts here. The host checkout lives in a temporary directory outside the
# repository; this stable in-container path works for every sample.
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
# A stack publishes on a free port it picks itself, so two stacks of one
# sample can run side by side. Another process can take that port between
# the pick and `up`; the stack then picks again, this many times at most.
STACK_PORT_ATTEMPTS = _integer("STACK_PORT_ATTEMPTS")
# How many stacks may be up on this host at once, all processes together:
# each is a JVM and a database, and an overloaded host turns into
# healthcheck timeouts, not into a slower run.
STACK_MAX_LIVE = _integer("STACK_MAX_LIVE")
# How many cases one score replays at once (`inspect eval --max-samples`).
# Every case still has its own stack; STACK_MAX_LIVE bounds them all.
SCORE_MAX_SAMPLES = _integer("SCORE_MAX_SAMPLES")

# --- the spans a case produces, kept before its stack is removed. ---------
# Every sample's stack names its collector `collector` and has it write
# this file (`prepare-repo-for-dataset`); a sample that does otherwise is
# prepared wrong, so neither is a per-run knob. The wait is the batch
# exporter's flush: spans arrive a few seconds after the request that made
# them, and `down -v` deletes the volume just after.
STACK_TRACES_SERVICE = "collector"
STACK_TRACES_FILE = "/traces/traces.jsonl"
TRACE_FLUSH_WAIT_S = 8

# --- who solves a run, and who judges it: named profiles in
# `tasks-config.yaml`, never `.env`. A profile is a choice, not a secret, so
# it is tracked; `.env` only holds the credentials its `model_env` names.
# `src/agents/` defines the agents a solve profile can name.
TASKS_CONFIG = ROOT / "tasks-config.yaml"
SOLVE_PROFILE_KEYS = (
    "agent",
    "agent_model",
    "agent_version",
    "answer_model",
    "model_env",
    "reasoning_effort",
    "model_args",
)
SCORE_PROFILE_KEYS = (
    "judge_model",
    "model_env",
    "reasoning_effort",
    "model_args",
    "max_tokens",
    "max_retries",
)
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")


def _profile(section: str, keys: tuple[str, ...], name: str) -> dict:
    """The profile ``name`` of ``section``, exactly as the file spells it.

    Every key is required and no other is allowed, so a typo is an error
    and not a value that silently never applies.
    """
    config = yaml.safe_load(TASKS_CONFIG.read_text())
    unknown_sections = sorted(
        set(config) - {"solve_profiles", "score_profiles"}
    )
    if unknown_sections:
        raise KeyError(f"{TASKS_CONFIG}: unknown {unknown_sections}")
    profiles = config[section]
    if name not in profiles:
        raise KeyError(
            f"no {section} entry {name!r} in {TASKS_CONFIG}; it has: "
            f"{', '.join(sorted(profiles))}"
        )
    chosen = profiles[name]
    missing = [key for key in keys if key not in chosen]
    unknown = sorted(set(chosen) - set(keys))
    if missing or unknown:
        raise KeyError(
            f"{section} {name!r} in {TASKS_CONFIG}: missing {missing}, "
            f"unknown {unknown}"
        )
    if chosen["reasoning_effort"] not in EFFORTS:
        raise ValueError(
            f"{section} {name!r}: reasoning_effort must be one of {EFFORTS}"
        )
    return {key: chosen[key] for key in keys}


def solve_profile(name: str) -> dict:
    """Who solves: the agent, its pin, the model that answers, its effort.

    Credentials are not part of it: `credentials` resolves `model_env`
    against `.env`.
    """
    return _profile("solve_profiles", SOLVE_PROFILE_KEYS, name)


def score_profile(name: str) -> dict:
    """Who judges: the model `trace_similarity` asks, and its budget."""
    return _profile("score_profiles", SCORE_PROFILE_KEYS, name)


def credentials(chosen: dict) -> dict[str, str]:
    """The values of the variables a profile's provider reads, from `.env`.

    Either kind of profile: both name their provider's variables in
    `model_env`.

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


# Case flows do `import settings`, so the repository root must be importable
# from every entry point — including a scorer running on a worker thread.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
