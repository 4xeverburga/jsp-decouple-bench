"""config.py — every tunable, path and environment read lives here.

Leaf module: imports nothing from this project. Anything that hardcodes a
path, a port, a timeout or a credential source elsewhere is a bug.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# --- storage -----------------------------------------------------------------
BENCH_DB = Path(os.environ.get("BENCH_DB", ROOT / "bench.db"))
SCHEMA_SQL = ROOT / "schema.sql"
SEEDS_DIR = Path(os.environ.get("BENCH_SEEDS_DIR", ROOT / "seeds"))
OUT_DIR = Path(os.environ.get("BENCH_OUT_DIR", ROOT / "out"))
RUNS_DIR = OUT_DIR / "runs"

# --- sample / stack ----------------------------------------------------------
COMPOSE_FILE_NAME = os.environ.get("BENCH_COMPOSE_FILE", "compose.yaml")
SAMPLE_ENV_FILE = ".env"
DOCKER = os.environ.get("BENCH_DOCKER", "docker")
COMPOSE = os.environ.get("BENCH_COMPOSE", "compose")
COMPOSE_PROJECT_PREFIX = "bench-"
STACK_UP_TIMEOUT_S = int(os.environ.get("STACK_UP_TIMEOUT_S", "900"))
KEEP_STACK = os.environ.get("KEEP_STACK", "") not in ("", "0", "false", "False")

# Host ports are allocated per run, so two runs never collide. Samples must
# publish `${BENCH_HTTP_PORT:-<default>}` / `${BENCH_DB_PORT:-<default>}`.
PORT_RANGE_START = int(os.environ.get("BENCH_PORT_START", "8300"))
PORT_RANGE_END = int(os.environ.get("BENCH_PORT_END", "8499"))

# --- determinism (never read from the host) ----------------------------------
LOCALE = "en-US"
TIMEZONE_ID = "UTC"
VIEWPORT = {"width": 1280, "height": 800}

# --- browser -----------------------------------------------------------------
BROWSER_ENGINE = os.environ.get("BENCH_BROWSER", "chromium")
HEADLESS = os.environ.get("BENCH_HEADLESS", "1") not in ("0", "false", "False")

# --- trace_similarity oracle -------------------------------------------------
# "none" keeps the gate at verdict="pending". A future oracle is a command
# that reads the trace document on stdin and prints {"value":0..1,...} on stdout.
TRACE_ORACLE = os.environ.get("BENCH_TRACE_ORACLE", "none")
TRACE_ORACLE_CMD = os.environ.get("BENCH_TRACE_ORACLE_CMD", "")


def load_env_file(path: Path, override: bool = False) -> dict[str, str]:
    """Load a KEY=VALUE file the way compose does. Never logs values.

    Existing shell variables win by default (same semantics as dotenv), so a
    captured terminal cannot silently override a sample's declared .env.
    """
    loaded: dict[str, str] = {}
    if not path.is_file():
        return loaded
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        loaded[key] = value
        if override or key not in os.environ:
            os.environ[key] = value
    return loaded
