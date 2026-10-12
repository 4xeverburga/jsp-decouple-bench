"""E2E flow: mamute/vote-flow__downvote-decrements-count

Self-contained: signs up its own author, asks its own question, then logs
in as the seeded moderator and downvotes the question through the vote
widget. Asserts the visible vote count goes 0 -> -1 and returns normalized
DOM snapshots before/after the downvote for parity replay.

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
    page.click("input[type=submit]")
    page.wait_for_load_state("networkidle")


def _ask_question(page, base_url):
    page.goto(base_url + "/ask")
    page.wait_for_load_state("networkidle")
    page.fill("input[name=title]", QUESTION_TITLE)
    page.fill("textarea[name=description]", QUESTION_BODY)
    page.fill("input[name=tagNames]", QUESTION_TAGS)
    # The 'watching' checkbox is checked by default; leave it as-is so the
    # arrange steps stay deterministic (Watcher rows are part of the DB delta).
    page.click("input[type=submit]")
    page.wait_for_load_state("networkidle")
    return page.url  # redirected to /{question.id}-{sluggedTitle}


def _login(page, base_url, email, password):
    page.goto(base_url + "/login")
    page.wait_for_load_state("networkidle")
    page.fill("input[name=email]", email)
    page.fill("input[name=password]", password)
    page.click("input[type=submit]")
    page.wait_for_load_state("networkidle")


def run(page, base_url):
    admin_user = os.environ["MAMUTE_ADMIN_USER"]
    admin_password = os.environ["MAMUTE_ADMIN_PASSWORD"]

    # --- arrange: author signs up and asks a question --------------------
    _signup_author(page, base_url)
    question_url = _ask_question(page, base_url)
    page.goto(base_url + "/logout")
    page.wait_for_load_state("networkidle")

    # --- act: moderator downvotes through the vote widget ----------------
    _login(page, base_url, admin_user, admin_password)
    page.goto(question_url)
    page.wait_for_load_state("networkidle")

    vote_container = page.locator(".vote-container").first
    count_before = vote_container.locator(".vote-count").inner_text().strip()
    dom_before = _normalize(page.content())

    with page.expect_response("**/voto/negativo") as resp_info:
        vote_container.locator("a.down-arrow").click()
    assert resp_info.value.status == 200, (
        "downvote POST failed with HTTP %d" % resp_info.value.status
    )
    page.wait_for_function(
        "() => {"
        "  const el = document.querySelector('.vote-container .vote-count');"
        "  return el && el.textContent.trim() !== '%s';" % count_before,
        timeout=5000,
    )

    count_after = vote_container.locator(".vote-count").inner_text().strip()
    dom_after = _normalize(page.content())

    assert count_after == "-1", (
        "expected vote count '-1' after downvote, got %r" % count_after
    )

    return {
        "question_url": question_url,
        "vote_count_before": count_before,
        "vote_count_after": count_after,
        "dom_before": dom_before,
        "dom_after": dom_after,
    }
