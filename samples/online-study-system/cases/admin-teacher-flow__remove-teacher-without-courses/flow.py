"""E2E flow:
online-study-system/admin-teacher-flow__remove-teacher-without-courses

The seeded admin removes 刘老师, who teaches no course, from the 教师
list (accepting the confirm dialog). The teacher and its login are
deleted, and the list no longer shows the row.

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
    dom_before = _normalize(page.content())
    assert NAME in dom_before, "teacher %r must exist first" % NAME

    # --- act: remove the teacher (accept the confirm() dialog) -----------
    page.once("dialog", lambda dialog: dialog.accept())
    _click(page, _row(page, NAME).locator("a", has_text="删除"))

    # --- after: back on the list without the row -------------------------
    assert LIST in page.url, "expected the teacher list, got %s" % page.url
    dom_after = _normalize(page.content())
    present = NAME in page.locator("tbody").inner_text()
    assert not present, "teacher %r must be gone" % NAME
    return {
        "dom_before": dom_before,
        "dom_after": dom_after,
        "removed_teacher_present_after": present,
    }
