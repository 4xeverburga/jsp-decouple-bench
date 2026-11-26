"""E2E flow: online-study-system/admin-course-flow__second-page-lists-the-rest

The case's seed adds eight courses, so the 课程 list holds twelve: ten on
page 1 and two on page 2. The seeded admin opens the list, follows the
pager's 2, goes back with 上一页 (page=1) and forward again with 最后一页
(page=2). Page 2 must list exactly the two rows past the first ten, and
page 1 the first ten again: the offset is the handler's to compute.
Nothing is written.

Credentials come from the harness-injected environment only
(OSS_ADMIN_USER / OSS_ADMIN_PASSWORD) — never hardcoded here.
"""

import os
import re

LIST = "/admin/showCourse"
FIRST = [
    "C语言从入门到放弃",
    "JAVA",
    "养猪入门",
    "从零开始入门炒股",
    "离散数学",
]
SECOND = ["软件工程", "线性代数"]


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
    with page.expect_navigation(wait_until="load"):
        page.locator(".pagination a", has_text=text).first.click()
    page.wait_for_load_state("networkidle")


def run(page, base_url):
    _login(page, base_url)
    _goto(page, base_url + LIST)
    dom_first = _rows(page, 10, FIRST, SECOND)

    # --- act: page 2, back to page 1, then the last page ------------------
    _follow(page, "2")
    dom_second = _rows(page, 2, SECOND, FIRST)
    _follow(page, "上一页")
    dom_previous = _rows(page, 10, FIRST, SECOND)
    _follow(page, "最后一页")
    dom_last = _rows(page, 2, SECOND, FIRST)

    return {
        "dom_first": dom_first,
        "dom_second": dom_second,
        "dom_previous": dom_previous,
        "dom_last": dom_last,
    }
