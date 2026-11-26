"""E2E flow: online-study-system/admin-teacher-flow__search-teacher-by-name

The seeded admin types 张 in the 教师 list's search box and presses 搜索.
selectTeacher lists the teachers whose name contains it: 张老师 only.
Nothing is written.

Credentials come from the harness-injected environment only
(OSS_ADMIN_USER / OSS_ADMIN_PASSWORD) — never hardcoded here.
"""

import os
import re

LIST = "/admin/showTeacher"
TERM = "张"
HIT = "张老师"
MISSES = ["李老师", "刘老师", "曹老师"]


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

    # --- act: search by part of a name -----------------------------------
    page.fill("#form1 input[name=name]", TERM)
    _click(page, page.locator("#sub"))

    # --- assert: only the matching teacher -------------------------------
    body = page.locator("tbody").inner_text()
    assert HIT in body, "expected %r in the results (%s)" % (HIT, page.url)
    leaked = [name for name in MISSES if name in body]
    assert not leaked, "unexpected %r in the results" % leaked
    names = [
        row.locator("td").nth(1).inner_text().strip()
        for row in page.locator("tbody tr").all()
    ]
    dom_after = _normalize(page.content())
    return {
        "dom_before": dom_before,
        "dom_after": dom_after,
        "result_names": names,
    }
