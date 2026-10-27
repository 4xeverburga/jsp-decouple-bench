"""E2E flow: online-study-system/admin-student-flow__add-student-creates-user

The seeded admin creates a student (测试学生) through the add-student form.
The app must insert the login account (default password, student role) and
the student profile (default balance 0), then redirect to the student list
where the new row must be visible.

Both dates are filled explicitly with fixed values — an empty date field
would make the flow depend on the current date and break determinism.

Credentials come from the harness-injected environment only
(OSS_ADMIN_USER / OSS_ADMIN_PASSWORD) — never hardcoded here.
"""
import os
import re

STUDENT_NAME = "测试学生"


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

    _goto(page, base_url + "/admin/showStudent")
    dom_before = _normalize(page.content())
    assert STUDENT_NAME not in dom_before, (
        "student %r must not exist before the create" % STUDENT_NAME
    )

    # --- act: fill the add-student form and submit -------------------------
    with page.expect_navigation(wait_until="load"):
        page.locator("button", has_text="添加学生信息").click()
    page.wait_for_load_state("networkidle")
    assert "/admin/addStudent" in page.url, (
        "expected the add-student form, got %s" % page.url
    )

    page.fill("input[name=name]", STUDENT_NAME)
    # sex radio 男 is checked by default — leave it as-is (deterministic)
    page.fill("input[name=birthday]", "2000-01-01")
    page.fill("input[name=registerTime]", "2020-01-01")
    with page.expect_navigation(wait_until="load"):
        page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")

    # --- after: redirected to the student list -----------------------------
    assert "/admin/showStudent" in page.url, (
        "expected redirect to /admin/showStudent, got %s" % page.url
    )
    dom_after = _normalize(page.content())
    new_student_row = page.locator("tr", has_text=STUDENT_NAME).first.inner_text().strip()
    assert STUDENT_NAME in new_student_row, (
        "student %r missing from the student list" % STUDENT_NAME
    )

    return {
        "dom_before": dom_before,
        "dom_after": dom_after,
        "new_student_row": new_student_row,
    }
