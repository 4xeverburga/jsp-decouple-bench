"""E2E flow:
online-study-system/admin-teacher-flow__add-teacher-name-taken-refused

The seeded admin tries to add a teacher named 李老师, a name the dump
already gives a login. addTeacher finds it and refuses with 该名称已被注册;
nothing is written.

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
    _goto(page, base_url + "/admin/addTeacher")
    dom_before = _normalize(page.content())

    # --- act: submit a name that is taken --------------------------------
    page.fill("input[name=name]", NAME)
    page.fill("input[name=birthday]", "1985-06-15")
    page.select_option("select[name=degree]", "博士")
    page.fill("input[name=registerTime]", "2020-01-01")
    _click(page, page.locator("button[type=submit]"))

    # --- assert: refused -------------------------------------------------
    error_text = _refused(page, "该名称已被注册")
    dom_after = _normalize(page.content())
    return {
        "dom_before": dom_before,
        "error_text": error_text,
        "dom_after": dom_after,
    }
