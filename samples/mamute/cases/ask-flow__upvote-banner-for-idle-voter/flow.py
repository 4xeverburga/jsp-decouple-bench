"""E2E flow: mamute/ask-flow__upvote-banner-for-idle-voter

Self-contained: signs up its own author, who asks a question. The case's
seed leaves the seeded moderator with a last upvote years back, as any user
who has not voted for a week. When the moderator opens the question,
showQuestion finds isVotingEnough() false and the page asks for an upvote
(question.banner.upvote). The author, who signed up just now, never sees
it: a new user counts as having voted.

Moderator credentials come from the harness-injected environment only
(MAMUTE_ADMIN_USER / MAMUTE_ADMIN_PASSWORD) — never hardcoded here.

The arrange user is deterministic (fixed email/password); every case
gets its own fresh stack, so consecutive runs are identical.
"""

import os
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


BANNER = "p.banner-mark-as-solution"


def run(page, base_url):
    admin_user = os.environ["MAMUTE_ADMIN_USER"]
    admin_password = os.environ["MAMUTE_ADMIN_PASSWORD"]

    # --- arrange: author asks --------------------------------------------
    _signup_author(page, base_url)
    _fill_question(page, base_url, QUESTION_TAGS, True)
    _submit(page)
    question_url = page.url
    assert page.locator(BANNER).count() == 0, (
        "a user who just signed up must not be asked to upvote (%s)"
        % question_url
    )
    _open(page, base_url + "/logout")

    # --- act: the idle moderator opens the question ----------------------
    _login(page, base_url, admin_user, admin_password)
    response = _open(page, question_url)

    # --- assert: the page asks for an upvote -----------------------------
    assert response.status == 200, (
        "the question must render, got HTTP %d" % response.status
    )
    banner = page.locator(BANNER)
    assert banner.count() == 1, (
        "expected one upvote banner for an idle voter, found %d (%s)"
        % (banner.count(), question_url)
    )
    banner_text = banner.first.inner_text().strip()
    dom_after = _normalize(page.content())

    return {
        "question_url": question_url,
        "banner_text": banner_text,
        "dom_after": dom_after,
    }
