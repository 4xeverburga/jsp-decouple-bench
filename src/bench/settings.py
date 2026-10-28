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
ARTIFACTS = Path(__file__).with_name("artifacts.py")
CORPUS = Path(__file__).with_name("corpus")
SANDBOX = Path(__file__).with_name("compose.yaml")

CHECKOUT = os.environ["BENCH_CHECKOUT"]
BASE_URL = os.environ["BENCH_BASE_URL"]

FRONT_SERVICE = "front"

# How long a flow waits for something it asked the app to render. A
# flow's own bound, not an infrastructure tunable.
CASE_TIMEOUT_MS = 60_000

# Case flows do `import config`, so the repository root must be importable
# from every entry point — including a scorer running on a worker thread.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
