"""E2E flow: online-study-system/select-course-flow__already-selected-refused

The seeded student 小明, already enrolled in course 1, presses 选课 on it
again in the course list: stuSelectedCourse refuses a course already
selected or taken, the balance is not charged and no enrollment is
added.

Credentials come from the harness-injected environment only
(OSS_STUDENT_USER / OSS_STUDENT_PASSWORD) — never hardcoded here.
"""

import os
import re

COURSE_NAME = "C语言从入门到放弃"
TOTAL_PERIODS = 20


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


def _login(page, base_url, who):
    _goto(page, base_url + "/login")
    page.fill("input[name=name]", os.environ[who + "_USER"])
    page.fill("input[name=password]", os.environ[who + "_PASSWORD"])
    with page.expect_navigation(wait_until="load"):
        page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")


def _press(page, button, scope):
    """Click a navigating button, inside `scope` (a page or a row)."""
    with page.expect_navigation(wait_until="load"):
        scope.locator("button", has_text=button).click()
    page.wait_for_load_state("networkidle")


def _course_row(page):
    return page.locator("tr", has_text=COURSE_NAME).first


def _progress(page):
    return page.input_value("input[name=progress]").strip()


def _study_to_end(page, base_url):
    """Open course 1's study page and press 下一学时 up to its last period."""
    _goto(page, base_url + "/student/selectedCourse")
    _press(page, "学习", _course_row(page))
    assert _progress(page) == "0", "expected seeded progress 0"
    for expected in range(1, TOTAL_PERIODS + 1):
        _press(page, "下一学时", page)
        assert _progress(page) == str(expected), (
            "expected progress %d, got %r" % (expected, _progress(page))
        )


def _refused(page, fragment):
    """The error page, carrying `fragment`, and its text."""
    error_text = page.locator("body").inner_text()
    assert fragment in error_text, "expected the refusal %r, got: %s" % (
        fragment,
        error_text[:300],
    )
    return error_text.strip()[:500]


def run(page, base_url):
    _login(page, base_url, "OSS_STUDENT")
    _goto(page, base_url + "/student/showCourse")
    dom_before = _normalize(page.content())

    # --- act: select a course already selected ---------------------------
    _press(page, "选课", _course_row(page))

    # --- assert: refused -------------------------------------------------
    error_text = _refused(page, "该门课程已经选过或修过")
    assert "selectedCourse" not in page.url, "the selection must not land"
    dom_after = _normalize(page.content())
    return {
        "dom_before": dom_before,
        "dom_after": dom_after,
        "error_text": error_text,
    }
