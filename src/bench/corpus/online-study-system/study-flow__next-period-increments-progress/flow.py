"""E2E flow: online-study-system/study-flow__next-period-increments-progress

The seeded student 小明 opens the study page for course 1 (C语言从入门到放弃,
enrolled at progress 0) and clicks 下一学时 (next period).  The stored
progress must go 0 -> 1 and the study page must show the new value.

Credentials come from the harness-injected environment only
(OSS_STUDENT_USER / OSS_STUDENT_PASSWORD) — never hardcoded here.
"""

import os
import re

COURSE_NAME = "C语言从入门到放弃"


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
    user = os.environ["OSS_STUDENT_USER"]
    password = os.environ["OSS_STUDENT_PASSWORD"]
    _goto(page, base_url + "/login")
    page.fill("input[name=name]", user)
    page.fill("input[name=password]", password)
    with page.expect_navigation(wait_until="load"):
        page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")


def run(page, base_url):
    _login(page, base_url)

    # --- arrange: open the study page for course 1 ------------------------
    _goto(page, base_url + "/student/selectedCourse")
    row = page.locator("tr", has_text=COURSE_NAME).first
    with page.expect_navigation(wait_until="load"):
        row.locator("button", has_text="学习").click()
    page.wait_for_load_state("networkidle")
    assert (
        "/student/startStudy" in page.url
        or "/student/study" in page.url
        or page.locator("input[name=progress]").count() > 0
    ), "expected the study page, got %s" % page.url

    progress_before = page.input_value("input[name=progress]").strip()
    dom_before = _normalize(page.content())

    # --- act: next period --------------------------------------------------
    with page.expect_navigation(wait_until="load"):
        page.locator("button", has_text="下一学时").click()
    page.wait_for_load_state("networkidle")

    page.wait_for_function(
        "() => document.querySelector('input[name=progress]').value !== '%s'"
        % progress_before,
        timeout=5000,
    )
    progress_after = page.input_value("input[name=progress]").strip()
    dom_after = _normalize(page.content())

    assert progress_after == "1", (
        "expected progress '1' after 下一学时, got %r" % progress_after
    )

    return {
        "progress_before": progress_before,
        "progress_after": progress_after,
        "dom_before": dom_before,
        "dom_after": dom_after,
    }
