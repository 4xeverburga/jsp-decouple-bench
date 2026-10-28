"""E2E flow: online-study-system/admin-student-flow__remove-student-cascades

The seeded admin removes the student 小明 (id 24) from the student list via
the 删除 link.  The link is guarded by a JS confirm() dialog, which the flow
accepts.  小明 is enrolled in courses 1 and 4, so the removal must cascade:
both enrollment rows, the student profile and the login account disappear.

Credentials come from the harness-injected environment only
(OSS_ADMIN_USER / OSS_ADMIN_PASSWORD) — never hardcoded here.
"""

import os
import re

STUDENT_NAME = "小明"


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
    assert STUDENT_NAME in dom_before, (
        "student %r must exist before the removal" % STUDENT_NAME
    )

    # --- act: remove the student (accept the confirm() dialog) -------------
    page.once("dialog", lambda dialog: dialog.accept())
    row = page.locator("tr", has_text=STUDENT_NAME).first
    with page.expect_navigation(wait_until="load"):
        row.locator("a", has_text="删除").click()
    page.wait_for_load_state("networkidle")

    # --- after: redirected to the student list -----------------------------
    assert "/admin/showStudent" in page.url, (
        "expected redirect to /admin/showStudent, got %s" % page.url
    )
    dom_after = _normalize(page.content())
    removed_present = STUDENT_NAME in dom_after
    assert not removed_present, (
        "student %r must disappear from the student list" % STUDENT_NAME
    )

    return {
        "dom_before": dom_before,
        "dom_after": dom_after,
        "removed_student_present_after": removed_present,
    }
