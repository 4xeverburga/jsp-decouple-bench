"""E2E flow: mamute/ask-flow__illegal-tag-refused

Self-contained: signs up its own author and asks a question with a new
tag that has characters a tag may not carry (tags.sanitizer.regex allows
letters, digits and "-"). The tag picker offers any typed term as a new
tag, so the refusal is the server's: the form comes back with the reason
and no question is saved.

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


ILLEGAL_TAG = "c++x"


def run(page, base_url):
    _signup_author(page, base_url)

    # --- act: ask with an illegal new tag --------------------------------
    dom_before = _fill_question(page, base_url, ILLEGAL_TAG, True)
    _submit(page)

    # --- assert: the form again, with the reason -------------------------
    assert page.locator("input[name=title]").count() == 1, (
        "a refused question must show the form again, got %s" % page.url
    )
    body = page.locator("body").inner_text()
    assert ILLEGAL_TAG in body, "the refusal must name the tag"
    dom_after = _normalize(page.content())

    return {
        "dom_before": dom_before,
        "dom_after": dom_after,
    }
