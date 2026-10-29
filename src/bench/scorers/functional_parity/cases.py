"""Playing one case: its flow, its golden, and the difference.

A case is a directory under `src/samples/<sample>/cases/`. Its `flow.py` drives
the app with Playwright and `expect.json` (the frozen artifacts and the
database delta). The golden is read as JSON; the flow is loaded by path,
because a case is data: adding one must not mean touching Python.
"""

import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import settings

from .artifacts import normalize


def load(path: Path, name: str):
    """A module from its file: no package layout to satisfy."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def golden(slug: str, case: str) -> dict:
    golden_file = settings.SAMPLES / slug / "cases" / case / "expect.json"
    return json.loads(golden_file.read_text())


def _screenshot(page, slug: str, case: str) -> str | None:
    """Stage the page a case ended on, under out/evidence.

    The name carries a random suffix so two runs of the same case — of the
    same manifest, with different trees — never write the same file. The
    scorer keeps the file only if the case actually fails.

    Best effort: a case that failed must report why it failed, not a second
    error from the camera.
    """
    target = settings.EVIDENCE / slug / f"{case}-{uuid4().hex[:8]}.png"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(target), full_page=True)
    except Exception:
        return None
    return str(target.relative_to(settings.ROOT))


def play(slug: str, case: str) -> dict:
    """Run the case's flow against the running stack; report the artifacts.

    A difference is not left as a list of keys: the page it happened on is
    written to out/evidence, because "the count differs" is not evidence.
    """
    from playwright.sync_api import sync_playwright

    case_dir = settings.SAMPLES / slug / "cases" / case
    flow = load(case_dir / "flow.py", f"flow_{case.replace('-', '_')}")
    expect = golden(slug, case)["artifacts"]
    base_url = settings.base_url()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=settings.HEADLESS)
        context = browser.new_context(
            viewport={
                "width": settings.VIEWPORT_WIDTH,
                "height": settings.VIEWPORT_HEIGHT,
            },
            locale=settings.LOCALE,
            timezone_id=settings.TIMEZONE_ID,
        )
        page = context.new_page()
        try:
            actual = normalize(flow.run(page, base_url), base_url)
            differing = [
                key for key in expect if actual.get(key) != expect[key]
            ]
            # Always take the shot: whether the case passes is not known
            # here. The rows are compared after the page is gone, so a
            # failure can be DB-only with the page looking right — and that
            # is precisely the failure worth a picture. The scorer keeps
            # the file only if something differs.
            shot = _screenshot(page, slug, case)
        except Exception:
            _screenshot(page, slug, case)
            raise
        finally:
            browser.close()

    return {"differing": differing, "screenshot": shot}
