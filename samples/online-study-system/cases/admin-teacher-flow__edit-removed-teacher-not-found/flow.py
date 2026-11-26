"""E2E flow:
online-study-system/admin-teacher-flow__edit-removed-teacher-not-found

The seeded admin opens the 教师 list in two tabs. In the second it removes
刘老师; the first still shows the row. Following 修改 there asks for a
teacher that is gone, and editTeacherUI refuses with 未找到该教师: the
real user's path to that check, since a fresh list no longer offers it.

Credentials come from the harness-injected environment only
(OSS_ADMIN_USER / OSS_ADMIN_PASSWORD) — never hardcoded here.
"""

import os
import re

LIST = "/admin/showTeacher"
NAME = "刘老师"


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
    _goto(page, base_url + "/login")
    page.fill("input[name=name]", os.environ["OSS_ADMIN_USER"])
    page.fill("input[name=password]", os.environ["OSS_ADMIN_PASSWORD"])
    with page.expect_navigation(wait_until="load"):
        page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")


def _click(page, locator):
    with page.expect_navigation(wait_until="load"):
        locator.click()
    page.wait_for_load_state("networkidle")


def _row(page, name):
    return page.locator("tbody tr", has_text=name).first


def _refused(page, fragment):
    """The error page, carrying `fragment`, and its text."""
    text = page.locator("body").inner_text()
    assert fragment in text, "expected the refusal %r, got: %s (%s)" % (
        fragment,
        text[:300],
        page.url,
    )
    return text.strip()[:500]


def run(page, base_url):
    _login(page, base_url)
    _goto(page, base_url + LIST)
    dom_stale = _normalize(page.content())

    # --- arrange: remove the teacher from a second tab -------------------
    other = page.context.new_page()
    _goto(other, base_url + LIST)
    other.once("dialog", lambda dialog: dialog.accept())
    _click(other, _row(other, NAME).locator("a", has_text="删除"))
    assert NAME not in other.locator("tbody").inner_text(), (
        "teacher %r was not removed (%s)" % (NAME, other.url)
    )
    other.close()

    # --- act: 修改 on the stale first tab --------------------------------
    _click(page, _row(page, NAME).locator("button", has_text="修改"))

    # --- assert: refused -------------------------------------------------
    error_text = _refused(page, "未找到该教师")
    dom_after = _normalize(page.content())
    return {
        "dom_stale": dom_stale,
        "error_text": error_text,
        "dom_after": dom_after,
    }
