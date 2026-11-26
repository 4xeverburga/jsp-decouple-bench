"""E2E flow: online-study-system/admin-teacher-flow__add-teacher-creates-user

The seeded admin opens the 教师 list, follows 添加教师信息 and submits
the form for a new teacher. The app creates its login and its teacher row,
then redirects to the list, where the new row must be visible.

Credentials come from the harness-injected environment only
(OSS_ADMIN_USER / OSS_ADMIN_PASSWORD) — never hardcoded here.
"""

import os
import re

LIST = "/admin/showTeacher"
NAME = "测试教师"


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
    assert NAME not in dom_before, "teacher %r exists already" % NAME

    # --- act: fill the add-teacher form and submit -----------------------
    _click(page, page.locator("button", has_text="添加教师信息"))
    assert "/admin/addTeacher" in page.url, (
        "expected the add-teacher form, got %s" % page.url
    )
    dom_form = _normalize(page.content())
    page.fill("input[name=name]", NAME)
    page.check("input[name=sex][value=女]")
    page.fill("input[name=birthday]", "1990-01-01")
    page.select_option("select[name=degree]", "硕士")
    page.fill("input[name=registerTime]", "2020-01-01")
    _click(page, page.locator("button[type=submit]"))

    # --- after: redirected to the teacher list ---------------------------
    assert LIST in page.url, "expected the teacher list, got %s" % page.url
    dom_after = _normalize(page.content())
    new_teacher_row = _row(page, NAME).inner_text().strip()
    assert NAME in new_teacher_row, "teacher %r missing" % NAME
    return {
        "dom_before": dom_before,
        "dom_form": dom_form,
        "dom_after": dom_after,
        "new_teacher_row": new_teacher_row,
    }
