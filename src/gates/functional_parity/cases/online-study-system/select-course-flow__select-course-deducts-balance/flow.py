"""E2E flow:
online-study-system/select-course-flow__select-course-deducts-balance

The seeded student 小明 (balance 80, already enrolled in courses 1 and 4)
selects 养猪入门 (course 7, price 10) from the all-courses page.  The app
deducts the price from the balance and enrolls the student, then redirects
to the selected-courses page where the new row must be visible.

Credentials come from the harness-injected environment only
(OSS_STUDENT_USER / OSS_STUDENT_PASSWORD) — never hardcoded here.
"""

import os
import re

COURSE_NAME = "养猪入门"


def _normalize(html):
    """Strip volatile markup so two runs of this flow are identical."""
    html = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<style\b.*?</style>", "", html, flags=re.S | re.I)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def _goto(page, url):
    # legacy app intermittently stalls a goto on a reused keep-alive
    # connection; one retry instead of sleeping
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

    # --- before: the all-courses page ------------------------------------
    _goto(page, base_url + "/student/showCourse")
    dom_before = _normalize(page.content())

    # --- act: select the course through its 选课 widget -------------------
    row = page.locator("tr", has_text=COURSE_NAME).first
    with page.expect_navigation(wait_until="load"):
        row.locator("button", has_text="选课").click()
    page.wait_for_load_state("networkidle")

    # --- after: redirected to the selected-courses page -------------------
    assert "/student/selectedCourse" in page.url, (
        "expected redirect to /student/selectedCourse, got %s" % page.url
    )
    dom_after = _normalize(page.content())
    selected_row = (
        page.locator("tr", has_text=COURSE_NAME).first.inner_text().strip()
    )
    assert COURSE_NAME in selected_row, (
        "course %r missing from the selected-courses page" % COURSE_NAME
    )

    return {
        "dom_before": dom_before,
        "dom_after": dom_after,
        "selected_row_after": selected_row,
    }
