"""src/harness/adapters/playwright/browser.py — `playwright@1` → BrowserPort.

Runs `cases/<sample>/<case>/flow.py` (the single source of truth for a
behaviour). Locale, timezone and viewport come from the case, falling back
to config.py — never from the host.
"""
from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import config
from src.errors import CaseError


class _ScreenshotPage:
    """Delegates to the real page, screenshotting after every goto/click."""

    def __init__(self, page: Any, images_dir: Path):
        self._page = page
        self._dir = images_dir
        self._step = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._page, name)

    def _shot(self, label: str) -> None:
        self._step += 1
        slug = re.sub(r"\W+", "_", label)[:60] or "step"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._page.screenshot(path=str(self._dir / f"{self._step:02d}-{slug}.png"),
                              full_page=True)

    def goto(self, url: str, **kw: Any) -> Any:
        result = self._page.goto(url, **kw)
        self._shot(urlparse(url).path or "root")
        return result

    def click(self, selector: str, **kw: Any) -> Any:
        result = self._page.click(selector, **kw)
        self._shot(f"after-click-{selector}")
        return result


class PlaywrightBrowser:
    def __init__(self, ctx: Any, options: dict[str, Any]):
        self.ctx = ctx
        self.options = options
        self._env_loaded = False

    # --- helpers -------------------------------------------------------------
    def _ensure_credentials(self, e2e: dict[str, Any]) -> None:
        if not self._env_loaded:
            config.load_env_file(Path(self.ctx.sample_location) / config.SAMPLE_ENV_FILE)
            self._env_loaded = True
        spec = e2e.get("credentials") or ""
        if not spec.startswith("env:"):
            return
        names = [n.strip() for n in spec[4:].split(",") if n.strip()]
        missing = [n for n in names if not os.environ.get(n)]
        if missing:
            raise CaseError(
                f"{self.ctx.sample['slug']}: missing credentials {missing} in "
                f"{config.SAMPLE_ENV_FILE} (never hardcode them in flow.py)"
            )

    def _load_flow(self, case_name: str) -> Any:
        path = self.ctx.flow_file(case_name)
        spec = importlib.util.spec_from_file_location(f"bench_case_{case_name}", path)
        if spec is None or spec.loader is None:  # pragma: no cover
            raise CaseError(f"cannot import {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not hasattr(module, "run"):
            raise CaseError(f"{path} defines no run(page, base_url)")
        return module

    def _execute(self, case_name: str, base_url: str,
                 images_dir: Path | None) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright  # local: db-init must not need it

        case = self.ctx.case(case_name)
        e2e = case.get("e2e") or {}
        self._ensure_credentials(e2e)
        flow = self._load_flow(case_name)

        with sync_playwright() as playwright:
            browser = getattr(playwright, config.BROWSER_ENGINE).launch(
                headless=config.HEADLESS)
            try:
                context = browser.new_context(
                    viewport=e2e.get("viewport") or dict(config.VIEWPORT),
                    locale=e2e.get("locale") or config.LOCALE,
                    timezone_id=e2e.get("timezone_id") or config.TIMEZONE_ID,
                )
                page = context.new_page()
                target = _ScreenshotPage(page, images_dir) if images_dir else page
                return flow.run(target, base_url)
            finally:
                browser.close()

    # --- BrowserPort ---------------------------------------------------------
    def run_case(self, case_name: str, base_url: str) -> dict[str, Any]:
        return self._execute(case_name, base_url, images_dir=None)

    def capture_case(self, case_name: str, base_url: str,
                     images_dir: Path) -> dict[str, Any]:
        return self._execute(case_name, base_url, images_dir=Path(images_dir))
