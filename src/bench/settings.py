"""Constants the bench runs with, and the one import bootstrap.

Nothing here is a tunable: the checkout under test and the URL its stack
publishes arrive from the environment, because Inspect owns the sandbox and
has already booted it by the time a scorer runs.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEEDS = ROOT / "seeds"

# One folder per sample: `<slug>/cases/` is the answer key, `<slug>/env/` the
# stack. Kept out of `bench/` because samples are data and there will be many.
SAMPLES = ROOT / "src" / "samples"

# What a failing case leaves behind: a screenshot of the page it ended on.
# The name carries a random suffix, so two runs of the same case cannot land
# on one file and a pass can never erase a failure's picture.
EVIDENCE = ROOT / "out" / "evidence"


# Read when asked, not at import: listing the manifests must not require
# a checkout, a published URL or a sandbox.
def checkout() -> str:
    return os.environ["BENCH_CHECKOUT"]


def base_url() -> str:
    return os.environ["BENCH_BASE_URL"]


# OpenCode's provider client; the bridge still answers with the eval's model.
OPENCODE_MODEL = "anthropic/claude-sonnet-4-5"

FRONT_SERVICE = "front"

# How long a flow waits for something it asked the app to render. A
# flow's own bound, not an infrastructure tunable.
CASE_TIMEOUT_MS = 60_000

# Case flows do `import config`, so the repository root must be importable
# from every entry point — including a scorer running on a worker thread.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
