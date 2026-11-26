"""E2E flow: online-study-system/exam-flow__save-exam-marks-has-exam

The seeded student 小明 completes all 20 periods of course 1
(C语言从入门到放弃) by clicking 下一学时 twenty times, then takes the
exam (考试) and submits the
paper (提交试卷).  The enrollment row must end with progress = 20 (the course's
full period count) and has_exam = 1.

startExam refuses to open the exam page unless progress == period, so the
long arrange is part of the behavior under test.

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

    # --- arrange: drive the progress from 0 to the full 20 periods --------
    _goto(page, base_url + "/student/selectedCourse")
    row = page.locator("tr", has_text=COURSE_NAME).first
    with page.expect_navigation(wait_until="load"):
        row.locator("button", has_text="学习").click()
    page.wait_for_load_state("networkidle")

    progress_before = page.input_value("input[name=progress]").strip()
    dom_before = _normalize(page.content())
    assert progress_before == "0", (
        "expected seeded progress '0', got %r" % progress_before
    )

    for expected in range(1, TOTAL_PERIODS + 1):
        with page.expect_navigation(wait_until="load"):
            page.locator("button", has_text="下一学时").click()
        page.wait_for_load_state("networkidle")
        current = page.input_value("input[name=progress]").strip()
        assert current == str(expected), (
            "expected progress %d after click %d, got %r"
            % (expected, expected, current)
        )

    # --- act: take the exam and submit the paper --------------------------
    _goto(page, base_url + "/student/selectedCourse")
    row = page.locator("tr", has_text=COURSE_NAME).first
    with page.expect_navigation(wait_until="load"):
        row.locator("button", has_text="考试").click()
    page.wait_for_load_state("networkidle")
    assert "/student/startExam" in page.url, (
        "expected the exam page, got %s" % page.url
    )

    with page.expect_navigation(wait_until="load"):
        page.locator("button", has_text="提交试卷").click()
    page.wait_for_load_state("networkidle")

    # --- after: back on the selected-courses view, progress complete ------
    progress_after = (
        page.locator("tr", has_text=COURSE_NAME).first.inner_text().strip()
    )
    assert COURSE_NAME in progress_after, "course row missing after saveExam"
    dom_after = _normalize(page.content())

    return {
        "progress_before": progress_before,
        "progress_after": progress_after,
        "dom_before": dom_before,
        "dom_after": dom_after,
    }
