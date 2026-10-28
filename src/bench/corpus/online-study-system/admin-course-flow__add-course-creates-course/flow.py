"""E2E flow: online-study-system/admin-course-flow__add-course-creates-course

The seeded admin creates a course (测试课程, taught by 李老师, 15 periods,
price 30) through the add-course form.  The app must insert the course row
and redirect to the course list where the new row must be visible.

Credentials come from the harness-injected environment only
(OSS_ADMIN_USER / OSS_ADMIN_PASSWORD) — never hardcoded here.
"""

import os
import re

COURSE_NAME = "测试课程"
TEACHER_NAME = "李老师"


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
    user = os.environ["OSS_ADMIN_USER"]
    password = os.environ["OSS_ADMIN_PASSWORD"]
    _goto(page, base_url + "/login")
    page.fill("input[name=name]", user)
    page.fill("input[name=password]", password)
    with page.expect_navigation(wait_until="load"):
        page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")


def run(page, base_url):
    _login(page, base_url)

    _goto(page, base_url + "/admin/showCourse")
    dom_before = _normalize(page.content())
    assert COURSE_NAME not in dom_before, (
        "course %r must not exist before the create" % COURSE_NAME
    )

    # --- act: fill the add-course form and submit --------------------------
    with page.expect_navigation(wait_until="load"):
        page.locator("button", has_text="添加课程信息").click()
    page.wait_for_load_state("networkidle")
    assert "/admin/addCourse" in page.url, (
        "expected the add-course form, got %s" % page.url
    )

    page.fill("input[name=name]", COURSE_NAME)
    page.select_option("select[name=teacherId]", label=TEACHER_NAME)
    page.fill("input[name=period]", "15")
    page.fill("input[name=price]", "30")
    with page.expect_navigation(wait_until="load"):
        page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")

    # --- after: redirected to the course list ------------------------------
    assert "/admin/showCourse" in page.url, (
        "expected redirect to /admin/showCourse, got %s" % page.url
    )
    dom_after = _normalize(page.content())
    new_course_row = (
        page.locator("tr", has_text=COURSE_NAME).first.inner_text().strip()
    )
    assert COURSE_NAME in new_course_row, (
        "course %r missing from the course list" % COURSE_NAME
    )

    return {
        "dom_before": dom_before,
        "dom_after": dom_after,
        "new_course_row": new_course_row,
    }
