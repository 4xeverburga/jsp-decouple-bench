"""E2E flow: mamute/vote-flow__upvote-then-downvote-switches

Self-contained: signs up its own author, asks its own question, then logs
in as the seeded moderator and upvotes the question through the vote
widget. The page is then reloaded and the down arrow clicked: the stored
upvote is replaced by a downvote, with its reputation events undone, so
the visible count goes 0 -> 1 -> -1 and only the down arrow is
highlighted.

Credentials come from the harness-injected environment only
(MAMUTE_ADMIN_USER / MAMUTE_ADMIN_PASSWORD) — never hardcoded here.
The arrange user is deterministic (fixed email/password); the orchestrator
resets the DB between test dirs, so consecutive runs are identical.
"""

import os
import re

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
UP = "a.up-arrow"
DOWN = "a.down-arrow"


def _normalize(html):
    """Strip volatile markup so two runs of this flow are identical."""
    html = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<style\b.*?</style>", "", html, flags=re.S | re.I)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def _signup_author(page, base_url):
    page.goto(base_url + "/sign-up")
    page.wait_for_load_state("networkidle")
    page.fill("#name", ARRANGE_NAME)
    page.fill("#email", ARRANGE_EMAIL)
    page.fill("#password", ARRANGE_PASSWORD)
    page.fill("#password-confirmation", ARRANGE_PASSWORD)
    with page.expect_navigation(wait_until="load"):
        page.click("input[type=submit]")
    page.wait_for_load_state("networkidle")


def _ask_question(page, base_url):
    page.goto(base_url + "/ask")
    page.wait_for_load_state("networkidle")
    page.fill("input[name=title]", QUESTION_TITLE)
    page.fill("textarea[name=description]", QUESTION_BODY)
    page.click(".select2-container")
    page.fill(".select2-input", QUESTION_TAGS)
    page.wait_for_selector(".select2-result-selectable", timeout=5000)
    page.click(".select2-result-selectable")
    with page.expect_navigation(wait_until="load"):
        page.click("input[type=submit]")
    page.wait_for_load_state("networkidle")
    return page.url


def _login(page, base_url, email, password):
    page.goto(base_url + "/login")
    page.wait_for_load_state("networkidle")
    page.fill("input[name=email]", email)
    page.fill("input[name=password]", password)
    with page.expect_navigation(wait_until="load"):
        page.click("input[type=submit]")
    page.wait_for_load_state("networkidle")


def _open(page, url):
    page.goto(url)
    page.wait_for_load_state("networkidle")
    return page.locator(".vote-container").first


def _click(page, container, arrow, route):
    """Click an arrow and wait until the widget has applied the answer."""
    with page.expect_response(route) as resp_info:
        container.locator(arrow).click()
    assert resp_info.value.status == 200, "%s failed with HTTP %d" % (
        route,
        resp_info.value.status,
    )
    page.wait_for_function(
        "() => !document.querySelector('.vote-container .vote-option.stop')",
        timeout=5000,
    )
    return container.locator(".vote-count").inner_text().strip()


def _voted(container, arrow):
    classes = container.locator(arrow).get_attribute("class") or ""
    return "voted" in classes.split()


def run(page, base_url):
    admin_user = os.environ["MAMUTE_ADMIN_USER"]
    admin_password = os.environ["MAMUTE_ADMIN_PASSWORD"]

    # --- arrange: author asks, moderator upvotes -------------------------
    _signup_author(page, base_url)
    question_url = _ask_question(page, base_url)
    page.goto(base_url + "/logout")
    page.wait_for_load_state("networkidle")
    _login(page, base_url, admin_user, admin_password)

    container = _open(page, question_url)
    count_before = container.locator(".vote-count").inner_text().strip()
    count_voted = _click(page, container, UP, "**/voto/positivo")
    assert count_voted == "1", "upvote should give '1', got %r" % count_voted

    # --- act: reload, then click the other arrow -------------------------
    container = _open(page, question_url)
    assert _voted(container, UP), (
        "after a reload the stored upvote must highlight the up arrow"
    )
    dom_before = _normalize(page.content())
    count_after = _click(page, container, DOWN, "**/voto/negativo")
    assert count_after == "-1", (
        "switching to a downvote should give '-1', got %r" % count_after
    )

    # --- after: a reload agrees with the widget ---------------------------
    container = _open(page, question_url)
    count_reloaded = container.locator(".vote-count").inner_text().strip()
    assert _voted(container, DOWN) and not _voted(container, UP), (
        "after the switch only the down arrow may be highlighted"
    )
    dom_after = _normalize(page.content())

    return {
        "question_url": question_url,
        "vote_count_before": count_before,
        "vote_count_voted": count_voted,
        "vote_count_after": count_after,
        "vote_count_reloaded": count_reloaded,
        "dom_before": dom_before,
        "dom_after": dom_after,
    }
