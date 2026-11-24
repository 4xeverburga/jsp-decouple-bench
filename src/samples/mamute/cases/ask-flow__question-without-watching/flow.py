"""E2E flow: mamute/ask-flow__question-without-watching

Self-contained: signs up its own author and asks a question with the
form's "watch" box cleared. The question is created like any other; the
row delta is what tells this case apart: no Watcher row, no
Question_Watchers row.

The arrange user is deterministic (fixed email/password); every case
gets its own fresh stack, so consecutive runs are identical.
"""

import re

from settings import CASE_TIMEOUT_MS

ARRANGE_EMAIL = "author@bench.test"
ARRANGE_PASSWORD = "bench-author-pass"
ARRANGE_NAME = "Bench Author"
QUESTION_TITLE = "How do I decouple a JSP frontend from its backend?"
QUESTION_BODY = (
    "I have a legacy JSP page that renders questions server side. "
    "What is the recommended way to expose the same data through REST "
    "endpoints instead of rendering HTML on the server?"
)
QUESTION_TAGS = "jsp"


def _normalize(html):
    """Strip volatile markup so two runs of this flow are identical."""
    html = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<style\b.*?</style>", "", html, flags=re.S | re.I)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def _open(page, url):
    response = page.goto(url)
    page.wait_for_load_state("networkidle")
    return response


def _signup_author(page, base_url):
    _open(page, base_url + "/sign-up")
    page.fill("#name", ARRANGE_NAME)
    page.fill("#email", ARRANGE_EMAIL)
    page.fill("#password", ARRANGE_PASSWORD)
    page.fill("#password-confirmation", ARRANGE_PASSWORD)
    with page.expect_navigation(wait_until="load"):
        page.click("input[type=submit]")
    page.wait_for_load_state("networkidle")


def _login(page, base_url, email, password):
    _open(page, base_url + "/login")
    page.fill("input[name=email]", email)
    page.fill("input[name=password]", password)
    with page.expect_navigation(wait_until="load"):
        page.click("input[type=submit]")
    page.wait_for_load_state("networkidle")


def _fill_question(page, base_url, tag, watching):
    """Fill the /ask form; select2 v3 hides the real tag input."""
    _open(page, base_url + "/ask")
    dom_form = _normalize(page.content())
    page.fill("input[name=title]", QUESTION_TITLE)
    page.fill("textarea[name=description]", QUESTION_BODY)
    page.click(".select2-container")
    page.fill(".select2-input", tag)
    page.wait_for_selector(
        ".select2-result-selectable", timeout=CASE_TIMEOUT_MS
    )
    page.click(".select2-result-selectable")
    box = page.locator("label.form-watch input[name=watching]")
    if watching:
        box.check()
    else:
        box.uncheck()
    return dom_form


def _submit(page):
    with page.expect_navigation(wait_until="load"):
        page.click("input[type=submit]")
    page.wait_for_load_state("networkidle")


def _watch_state(page):
    span = page.locator("a.watch span").first
    classes = span.get_attribute("class") or ""
    if "icon-eye-off" in classes:
        return "not-watching"
    if "icon-eye" in classes:
        return "watching"
    return "unknown"


def run(page, base_url):
    _signup_author(page, base_url)

    # --- act: ask with the watch box cleared -----------------------------
    dom_before = _fill_question(page, base_url, QUESTION_TAGS, False)
    _submit(page)

    # --- assert: the question page, not watching -------------------------
    question_url = page.url
    title_after = page.locator(".question-title, h1").first.inner_text()
    assert QUESTION_TITLE in title_after, title_after
    watch_state_after = _watch_state(page)
    assert watch_state_after == "not-watching", watch_state_after
    dom_after = _normalize(page.content())

    return {
        "question_url": question_url,
        "dom_before": dom_before,
        "dom_after": dom_after,
        "watch_state_after": watch_state_after,
    }
