"""E2E flow: online-study-system/select-course-flow__insufficient-balance-blocks-selection

The seeded student 小红 (balance 0) tries to select 从零开始入门炒股
(course 8, price 74).  The app must reject the selection with the
insufficient-balance error page and leave the database untouched.

Credentials come from the harness-injected environment only
(OSS_STUDENT2_USER / OSS_STUDENT2_PASSWORD) — never hardcoded here.

DB note: the expected delta is intentionally EMPTY — rejection is the
behavior, and no row may change.  db_state therefore carries no signal for
this test; the assertion lives in the DOM (error page rendered).
"""
import os
import re

COURSE_NAME = "从零开始入门炒股"
ERROR_FRAGMENT = "余额不足"


def _normalize(html):
    html = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<style\b.*?</style>", "", html, flags=re.S | re.I)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def _goto(page, url):
    try:
        page.goto(url, wait_until="load")
    except Exception:
        page.goto(url, wait_until="load")
    page.wait_for_load_state("networkidle")


def _login(page, base_url):
    user = os.environ["OSS_STUDENT2_USER"]
    password = os.environ["OSS_STUDENT2_PASSWORD"]
    _goto(page, base_url + "/login")
    page.fill("input[name=name]", user)
    page.fill("input[name=password]", password)
    with page.expect_navigation(wait_until="load"):
        page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")


def run(page, base_url):
    _login(page, base_url)

    _goto(page, base_url + "/student/showCourse")
    dom_before = _normalize(page.content())

    # --- act: try to select a course the balance cannot afford ------------
    row = page.locator("tr", has_text=COURSE_NAME).first
    with page.expect_navigation(wait_until="load"):
        row.locator("button", has_text="选课").click()
    page.wait_for_load_state("networkidle")

    # --- after: the error page is rendered (server-side forward) ----------
    dom_after = _normalize(page.content())
    error_text = page.locator("body").inner_text()
    assert ERROR_FRAGMENT in error_text, (
        "expected insufficient-balance error containing %r, got: %s"
        % (ERROR_FRAGMENT, error_text[:300])
    )
    assert "selectedCourse" not in page.url, (
        "selection must not land on the selected-courses page"
    )

    return {
        "dom_before": dom_before,
        "dom_after": dom_after,
        "error_text": error_text.strip()[:500],
    }
