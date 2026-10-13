#!/usr/bin/env python3
"""Run one bench e2e flow against a running sample stack.

Usage:
  .venv/bin/python scripts/run_flow.py <sample> <test>
      e.g. run_flow.py mamute answer-flow__answer-appears

Generic counterpart of capture_delta.py (which is mamute-specific and also
freezes the golden delta). This runner only executes the flow: it loads the
sample's .env (credentials the flows read from the environment), applies the
spec.json viewport/locale/timezone, imports bench/e2e/<sample>/<test>/flow.py
and calls run(page, base_url). Prints the artifacts dict as JSON.

The base URL comes from the sample's coverage.env (COVERAGE_BASE_URL) or the
<SAMPLE>_BASE_URL environment variable.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent

if len(sys.argv) != 3:
    sys.exit(__doc__)
sample, test = sys.argv[1], sys.argv[2]

test_dir = BENCH / "bench" / "e2e" / sample / test
if not (test_dir / "flow.py").exists():
    sys.exit(f"no such test: bench/e2e/{sample}/{test}/flow.py")


def load_kv(path):
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


coverage = load_kv(BENCH / "environments" / sample / "coverage.env")
if not coverage.get("COVERAGE_BASE_URL"):
    sys.exit(f"missing COVERAGE_BASE_URL in environments/{sample}/coverage.env")

# credentials the flows read from the harness-injected environment only
for k, v in load_kv(BENCH / coverage.get("COVERAGE_ENV_FILE", "")).items():
    os.environ.setdefault(k, v)

base_url = os.environ.get(f"{sample.upper()}_BASE_URL", coverage["COVERAGE_BASE_URL"])

spec = {}
spec_path = test_dir / "spec.json"
if spec_path.exists():
    spec = json.loads(spec_path.read_text())

# flow.py is the single source of truth for the behavior
flow_spec = importlib.util.spec_from_file_location("bench_flow", test_dir / "flow.py")
flow = importlib.util.module_from_spec(flow_spec)
flow_spec.loader.exec_module(flow)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        viewport=spec.get("viewport", {"width": 1280, "height": 800}),
        locale=spec.get("locale", "en-US"),
        timezone_id=spec.get("timezone_id", "UTC"),
    )
    page = context.new_page()
    artifacts = flow.run(page, base_url)
    browser.close()

print(json.dumps(artifacts, indent=2))
