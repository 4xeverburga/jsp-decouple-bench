"""E2E flow: online-study-system/teacher-mark-flow__save-mark-sets-grade

Arrange: the seeded student 小明 completes course 1 (C语言从入门到放弃) —
advances all 20 periods and submits the exam — because no seeded enrollment
combines has_exam = 1 with mark = null (course 4 is seeded with mark 10),
and the mark page refuses students who have not taken the exam.

Act: the course's teacher 李老师 opens the grade page for course 1, where
小明 now shows as unmarked, enters 85 and saves it.  The enrollment row's
mark must go null -> 85 and the grade page must show it.

Legacy quirk: the mark page's visible 提交 button is broken (its onClick
navigates via GET and drops the mark field).  The flow submits the form
through its real POST action instead — the behavior under test is the
saveMark endpoint, not the broken widget.

Credentials come from the harness-injected environment only
(OSS_STUDENT_USER / OSS_TEACHER_USER / OSS_TEACHER_PASSWORD) — never
hardcoded here.
"""

import os
import re

COURSE_NAME = "C语言从入门到放弃"
STUDENT_NAME = "小明"
TOTAL_PERIODS = 20
MARK = "85"


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


def _login(page, base_url, user_env):
    user = os.environ[user_env]
    password = os.environ[user_env.replace("_USER", "_PASSWORD")]
    _goto(page, base_url + "/login")
    page.fill("input[name=name]", user)
    page.fill("input[name=password]", password)
    with page.expect_navigation(wait_until="load"):
        page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")


def run(page, base_url):
    # --- arrange: 小明 completes course 1 (all periods + exam) ------------
    _login(page, base_url, "OSS_STUDENT_USER")

    _goto(page, base_url + "/student/selectedCourse")
    row = page.locator("tr", has_text=COURSE_NAME).first
    with page.expect_navigation(wait_until="load"):
        row.locator("button", has_text="学习").click()
    page.wait_for_load_state("networkidle")

    for expected in range(1, TOTAL_PERIODS + 1):
        with page.expect_navigation(wait_until="load"):
            page.locator("button", has_text="下一学时").click()
        page.wait_for_load_state("networkidle")
        current = page.input_value("input[name=progress]").strip()
        assert current == str(expected), (
            "expected progress %d during arrange, got %r" % (expected, current)
        )

    _goto(page, base_url + "/student/selectedCourse")
    row = page.locator("tr", has_text=COURSE_NAME).first
    with page.expect_navigation(wait_until="load"):
        row.locator("button", has_text="考试").click()
    page.wait_for_load_state("networkidle")
    with page.expect_navigation(wait_until="load"):
        page.locator("button", has_text="提交试卷").click()
    page.wait_for_load_state("networkidle")

    # switch actor: log the student out, log the teacher in
    _goto(page, base_url + "/logout")
    page.wait_for_load_state("networkidle")

    # --- act: the teacher grades the completed course ----------------------
    _login(page, base_url, "OSS_TEACHER_USER")

    _goto(page, base_url + "/teacher/showCourse")
    row = page.locator("tr", has_text=COURSE_NAME).first
    with page.expect_navigation(wait_until="load"):
        row.locator("button", has_text="课程管理").click()
    page.wait_for_load_state("networkidle")
    assert "/teacher/gradeCourse" in page.url, (
        "expected the grade page, got %s" % page.url
    )

    grade_row = page.locator("tr", has_text=STUDENT_NAME).first
    mark_before = grade_row.inner_text().strip()
    dom_before = _normalize(page.content())
    assert "未打分" in mark_before, (
        "expected the student to be unmarked before the save, got: %s"
        % mark_before
    )

    with page.expect_navigation(wait_until="load"):
        grade_row.locator("button", has_text="打分").click()
    page.wait_for_load_state("networkidle")
    assert "/teacher/mark" in page.url, (
        "expected the mark page, got %s" % page.url
    )

    page.fill("input[name=mark]", MARK)
    with page.expect_navigation(wait_until="load"):
        page.evaluate("document.getElementById('editfrom').submit()")
    page.wait_for_load_state("networkidle")

    # --- after: back on the grade page with the mark shown ----------------
    assert "/teacher/gradeCourse" in page.url, (
        "expected redirect to the grade page, got %s" % page.url
    )
    grade_row = page.locator("tr", has_text=STUDENT_NAME).first
    mark_after = grade_row.inner_text().strip()
    dom_after = _normalize(page.content())

    assert MARK in mark_after, (
        "expected mark %r on the grade page, got: %s" % (MARK, mark_after)
    )

    return {
        "mark_before": mark_before,
        "mark_after": mark_after,
        "dom_before": dom_before,
        "dom_after": dom_after,
    }
