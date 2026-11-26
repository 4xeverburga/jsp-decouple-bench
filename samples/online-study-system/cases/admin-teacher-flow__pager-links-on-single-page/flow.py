"""E2E flow: online-study-system/admin-teacher-flow__pager-links-on-single-page

The seeded admin opens the 教师 list. Every row fits on page 1 (ten a
page), but the pager always offers 最后一页 (page=1, the last page) and
上一页 (page=0 on the first page). Both must show the same first page
again: the list handler reads a missing page, page 0 and page 1 as three
requests and answers them alike. Nothing is written.

Credentials come from the harness-injected environment only
(OSS_ADMIN_USER / OSS_ADMIN_PASSWORD) — never hardcoded here.
"""

import os
import re

LIST = "/admin/showTeacher"
NAMES = ["李老师", "张老师", "刘老师", "曹老师"]


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


def _rows(page, count, present, absent):
    """Assert the page lists `count` rows, with and without these names."""
    rows = page.locator("tbody tr")
    assert rows.count() == count, "%d rows, expected %d (%s)" % (
        rows.count(),
        count,
        page.url,
    )
    body = page.locator("tbody").inner_text()
    missing = [name for name in present if name not in body]
    assert not missing, "missing %r (%s)" % (missing, page.url)
    leaked = [name for name in absent if name in body]
    assert not leaked, "unexpected %r (%s)" % (leaked, page.url)
    return _normalize(page.content())


def _follow(page, text):
    _click(page, page.locator(".pagination a", has_text=text).first)


def run(page, base_url):
    _login(page, base_url)
    _goto(page, base_url + LIST)
    dom_before = _rows(page, 4, NAMES, [])

    # --- act: the pager's last-page link, then its previous-page link ----
    _follow(page, "最后一页")
    dom_last = _rows(page, 4, NAMES, [])
    _follow(page, "上一页")
    dom_previous = _rows(page, 4, NAMES, [])
    return {
        "dom_before": dom_before,
        "dom_last": dom_last,
        "dom_previous": dom_previous,
    }
