"""E2E flow:
online-study-system/admin-teacher-flow__remove-teacher-with-courses-refused

The seeded admin tries to remove 李老师, who teaches a course in the
dump. removeTeacher refuses with 该老师存在相应课程,无法删除 and nothing is
deleted; the list, opened again, still shows the row.

Credentials come from the harness-injected environment only
(OSS_ADMIN_USER / OSS_ADMIN_PASSWORD) — never hardcoded here.
"""

import os
import re

LIST = "/admin/showTeacher"
NAME = "李老师"


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

    # --- act: remove a teacher who still has a course --------------------
    page.once("dialog", lambda dialog: dialog.accept())
    _click(page, _row(page, NAME).locator("a", has_text="删除"))

    # --- assert: refused, and the row stays ------------------------------
    error_text = _refused(page, "该老师存在相应课程")
    _goto(page, base_url + LIST)
    assert NAME in page.locator("tbody").inner_text(), (
        "teacher %r must still be listed" % NAME
    )
    dom_after = _normalize(page.content())
    return {
        "dom_before": dom_before,
        "error_text": error_text,
        "dom_after": dom_after,
    }
