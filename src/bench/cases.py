"""Playing one case: its flow, its golden, and the difference.

A case is a directory holding `flow.py` (drives the app with Playwright) and
`expect.json` (the frozen artifacts and the database delta). Both are loaded
by path, because a case is data: adding one must not mean touching Python.
"""

import importlib.util
import json
from pathlib import Path

from . import settings
from .settings import ARTIFACTS, CORPUS


def load(path: Path, name: str):
    """A module from its file: no package layout to satisfy."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def golden(slug: str, case: str) -> dict:
    return json.loads((CORPUS / slug / case / "expect.json").read_text())


def play(slug: str, case: str) -> dict:
    """Run the case's flow against the running stack; report the artifacts."""
    from playwright.sync_api import sync_playwright

    normalize = load(ARTIFACTS, "bench_artifacts").normalize
    case_dir = CORPUS / slug / case
    flow = load(case_dir / "flow.py", f"flow_{case.replace('-', '_')}")
    expect = golden(slug, case)["artifacts"]
    base_url = settings.base_url()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="UTC",
        )
        page = context.new_page()
        try:
            actual = normalize(flow.run(page, base_url), base_url)
        finally:
            browser.close()

    return {
        "differing": [key for key in expect if actual.get(key) != expect[key]]
    }
