"""E2E flow: online-study-system/out-course-flow__out-course-deletes-enrollment

The seeded student 小明 drops course 1 (C语言从入门到放弃) from the
selected-courses page via the 退课 link.  The link is guarded by a JS
confirm() dialog, which the flow accepts; the app must delete the enrollment
row and redirect back to the selected-courses page without the dropped
course.

Course 1 is used because it is the only enrollment with has_exam = 0 — the
selected-courses page lists unfinished courses only (course 4, the other
seeded enrollment, is completed and lives on the over-courses page, which
has no drop widget).

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

    _goto(page, base_url + "/student/selectedCourse")
    dom_before = _normalize(page.content())
    assert COURSE_NAME in dom_before, (
        "course %r must be enrolled before the drop" % COURSE_NAME
    )

    # --- act: drop the course (accept the confirm() dialog) ---------------
    page.once("dialog", lambda dialog: dialog.accept())
    row = page.locator("tr", has_text=COURSE_NAME).first
    with page.expect_navigation(wait_until="load"):
        row.locator("a", has_text="退课").click()
    page.wait_for_load_state("networkidle")

    # --- after: redirected to the selected-courses page -------------------
    assert "/student/selectedCourse" in page.url, (
        "expected redirect to /student/selectedCourse, got %s" % page.url
    )
    dom_after = _normalize(page.content())
    dropped_present = COURSE_NAME in dom_after
    assert not dropped_present, (
        "course %r must disappear from the selected-courses page" % COURSE_NAME
    )

    return {
        "dom_before": dom_before,
        "dom_after": dom_after,
        "dropped_course_present_after": dropped_present,
    }
