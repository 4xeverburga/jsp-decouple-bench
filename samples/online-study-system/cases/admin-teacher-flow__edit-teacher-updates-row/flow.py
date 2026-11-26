"""E2E flow: online-study-system/admin-teacher-flow__edit-teacher-updates-row

The seeded admin follows 修改 on 刘老师's row, changes sex, birthday and
degree, and submits. The list must show the edited row; the name and the
register date, read-only on the form, keep their values.

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

    # --- act: open the edit form and change three fields -----------------
    _click(page, _row(page, NAME).locator("button", has_text="修改"))
    assert "/admin/editTeacher" in page.url, (
        "expected the edit form, got %s" % page.url
    )
    dom_form = _normalize(page.content())
    page.check("input[name=sex][value=女]")
    page.fill("input[name=birthday]", "1980-05-05")
    page.select_option("select[name=degree]", "博士")
    _click(page, page.locator("button[type=submit]"))

    # --- after: back on the list with the new values ---------------------
    assert LIST in page.url, "expected the teacher list, got %s" % page.url
    edited_row = _row(page, NAME).inner_text().strip()
    assert "博士" in edited_row and "女" in edited_row, (
        "edit not shown: %r" % edited_row
    )
    dom_after = _normalize(page.content())
    return {
        "dom_before": dom_before,
        "dom_form": dom_form,
        "dom_after": dom_after,
        "edited_row": edited_row,
    }
