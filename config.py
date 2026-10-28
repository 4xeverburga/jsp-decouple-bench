"""config.py — every tunable, path and environment read lives here.

Leaf module: imports nothing from this project. There are NO defaults in
code: every value comes from `<repo>/.env` (template: `.env.example`) and a
missing key is an error. The shell environment is deliberately not consulted,
so a polluted terminal can never change a measurement.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"

if not ENV_FILE.is_file():
    raise RuntimeError(f"{ENV_FILE} not found — copy .env.example to .env")
_ENV = dotenv_values(ENV_FILE)


def _req(name: str) -> str:
    value = _ENV.get(name)
    if value is None:
        raise RuntimeError(
            f"{name} is not set in {ENV_FILE} (see .env.example)"
        )
    return value


def _flag(name: str) -> bool:
    return _req(name) not in ("", "0", "false", "False")


def _path(name: str) -> Path:
    return ROOT / _req(name)  # absolute values win over ROOT


# --- logging -----------------------------------------------------------------
# Progress goes to stderr; stdout stays the one machine-readable value a
# command produces (a run_id). Nothing else may invent a level or a cadence.
LOG_LEVEL = _req("BENCH_LOG_LEVEL")
LOG_HEARTBEAT_S = int(_req("BENCH_HEARTBEAT_S"))

# --- storage -----------------------------------------------------------------
BENCH_DB = _path("BENCH_DB")
SCHEMA_SQL = ROOT / "schema.sql"
SEEDS_DIR = _path("BENCH_SEEDS_DIR")
OUT_DIR = _path("BENCH_OUT_DIR")
RUNS_DIR = OUT_DIR / "runs"
# One bare mirror per sample, fetched from SAMPLE.source. Runs clone out of
# it, so the sandbox a run owns never sits next to another checkout.
SAMPLE_CACHE_DIR = OUT_DIR / "cache"

# --- sample / stack ----------------------------------------------------------
COMPOSE_FILE_NAME = _req("BENCH_COMPOSE_FILE")
SAMPLE_ENV_FILE = _req("BENCH_SAMPLE_ENV_FILE")
DOCKER = _req("BENCH_DOCKER")
COMPOSE = _req("BENCH_COMPOSE")
COMPOSE_PROJECT_PREFIX = _req("BENCH_COMPOSE_PROJECT_PREFIX")
STACK_UP_TIMEOUT_S = int(_req("STACK_UP_TIMEOUT_S"))
STACK_POLL_INTERVAL_S = int(_req("STACK_POLL_INTERVAL_S"))
STACK_PROBE_TIMEOUT_S = int(_req("STACK_PROBE_TIMEOUT_S"))
KEEP_STACK = _flag("KEEP_STACK")

# Host ports are allocated per run, so two runs never collide. Samples must
# publish `${BENCH_HTTP_PORT:-<default>}` / `${BENCH_DB_PORT:-<default>}`.
PORT_RANGE_START = int(_req("BENCH_PORT_START"))
PORT_RANGE_END = int(_req("BENCH_PORT_END"))

# --- determinism (goldens are captured with these; change them deliberately) -
LOCALE = _req("BENCH_LOCALE")
TIMEZONE_ID = _req("BENCH_TIMEZONE_ID")
VIEWPORT = {
    "width": int(_req("BENCH_VIEWPORT_WIDTH")),
    "height": int(_req("BENCH_VIEWPORT_HEIGHT")),
}

# How long a flow waits for the app to render a result (the graded outcome,
# a widget list). A wait that expires is a failed assertion, not a crash.
CASE_TIMEOUT_MS = int(_req("BENCH_CASE_TIMEOUT_MS"))

# --- browser -----------------------------------------------------------------
BROWSER_ENGINE = _req("BENCH_BROWSER")
HEADLESS = _flag("BENCH_HEADLESS")

# --- agent harness -----------------------------------------------------------
# There is no harness registry and no default agent: one adapter runs the
# command the run was given, with the prompt on stdin. Both the label
# (`--harness`, recorded in TASK_RUN.harness) and the command
# (`--harness-cmd`) are required on every run, so a command kept in `.env`
# can never outlive the model it was written for.
HARNESS_TIMEOUT_S = int(_req("BENCH_HARNESS_TIMEOUT_S"))


# --- trace_similarity oracle -------------------------------------------------
# "none" keeps the gate at verdict="pending". A future oracle is a command
# that reads the trace document on stdin and prints {"value":0..1,...} on
# stdout.
TRACE_ORACLE = _req("BENCH_TRACE_ORACLE")
TRACE_ORACLE_CMD = _req("BENCH_TRACE_ORACLE_CMD")


def load_env_file(path: Path) -> dict[str, str]:
    """Load a sample's .env into os.environ (existing shell variables win).

    Never logs values.
    """
    values = {k: v for k, v in dotenv_values(path).items() if v is not None}
    for key, value in values.items():
        if key not in os.environ:
            os.environ[key] = value
    return values
