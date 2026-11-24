"""E2E flow: online-study-system/admin-course-flow__pager-links-on-single-page

The seeded admin opens the 课程 list. Every row fits on page 1 (ten a
page), but the pager always offers 最后一页 (page=1, the last page) and
上一页 (page=0 on the first page, which upPageNo leaves at 0). Both must
show the same first page again: the list handler reads a missing page,
page 0 and page 1 as three requests and answers them alike. Nothing is
written.

Credentials come from the harness-injected environment only
(OSS_ADMIN_USER / OSS_ADMIN_PASSWORD) — never hardcoded here.
"""

import os
import re

LIST = "/admin/showCourse"
NAMES = ["C语言从入门到放弃", "JAVA", "养猪入门", "从零开始入门炒股"]


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


def _follow(page, text):
    """Follow a pager link and return the page it lands on."""
    with page.expect_navigation(wait_until="load"):
        page.locator(".pagination a", has_text=text).first.click()
    page.wait_for_load_state("networkidle")
    body = page.locator("tbody").inner_text()
    missing = [name for name in NAMES if name not in body]
    assert not missing, "%s lost rows %r (%s)" % (text, missing, page.url)
    return _normalize(page.content())


def run(page, base_url):
    _login(page, base_url)
    _goto(page, base_url + LIST)
    dom_before = _normalize(page.content())

    # --- act: the pager's last-page link, then its previous-page link ----
    dom_last = _follow(page, "最后一页")
    dom_previous = _follow(page, "上一页")

    return {
        "dom_before": dom_before,
        "dom_last": dom_last,
        "dom_previous": dom_previous,
    }
