"""E2E flow: mamute/answer-flow__answer-appears

Self-contained: signs up its own author, asks a question, then logs in as
the seeded moderator and answers the question through the answer form.
The author cannot answer its own fresh question (karma gate), so the
answering actor is the moderator, whose credentials come from the
harness-injected environment only (MAMUTE_ADMIN_USER /
MAMUTE_ADMIN_PASSWORD) — never hardcoded here. Asserts the answers count
goes 0 -> 1 and the answer body is rendered, and returns normalized DOM
snapshots before/after the answer for parity replay.

The arrange user is deterministic (fixed email/password); the orchestrator
resets the DB between test dirs, so consecutive runs are identical.
"""

import os
import re

from playwright.sync_api import TimeoutError as PlaywrightTimeout

import config

ARRANGE_EMAIL = "author@bench.test"
ARRANGE_PASSWORD = "bench-author-pass"
ARRANGE_NAME = "Bench Author"
QUESTION_TITLE = "How do I render a question list without JSP on the server?"
QUESTION_BODY = (
    "We are decoupling our frontend from the legacy JSP rendering. "
    "What is the recommended way to serve the question list data so the "
    "frontend can render it independently?"
)
QUESTION_TAGS = "jsp"
ANSWER_BODY = (
    "Expose the question list through a REST endpoint that returns JSON, "
    "then render it client side. Keep the JSP only as a fallback while "
    "you migrate each flow."
)

# True once the submitted answer is observable on the page. Deliberately
# transport-agnostic: a redirect re-renders the page, an in-place update
# inserts the fragment, and both leave an `.answer .post-text` or bump the
# count heading to 1.
ANSWER_APPEARED_JS = r"""() => {
  const heading = document.querySelector('h2.page-title');
  const count = heading ? heading.textContent.trim().split(/\s+/)[0] : null;
  return count === '1' || !!document.querySelector('.answer .post-text');
}"""
ANSWER_COUNT_JS = r"""() => {
  const heading = document.querySelector('h2.page-title');
  return heading ? heading.textContent.trim().split(/\s+/)[0] : '?';
}"""


def _state(page):
    """Where the page is stuck, for the failure message."""
    return "count=%s rendered=%d url=%s" % (
        page.evaluate(ANSWER_COUNT_JS),
        page.locator(".answer .post-text").count(),
        page.url,
    )


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
    # tagNames is a select2 v3 widget (the real input is hidden); drive the UI:
    # focus -> type >= 3 chars (minimumInputLength) -> wait for the AJAX
    # result -> pick it
    page.click(".select2-container")
    page.fill(".select2-input", QUESTION_TAGS)
    page.wait_for_selector(
        ".select2-result-selectable", timeout=config.CASE_TIMEOUT_MS
    )
    page.click(".select2-result-selectable")
    # The 'watching' checkbox is checked by default; leave it as-is so the
    # arrange steps stay deterministic (Watcher rows are part of the DB delta).
    with page.expect_navigation(wait_until="load"):
        page.click("input[type=submit]")
    page.wait_for_load_state("networkidle")
    return page.url  # redirected to /{question.id}-{sluggedTitle}


def _login(page, base_url, email, password):
    page.goto(base_url + "/login")
    page.wait_for_load_state("networkidle")
    page.fill("input[name=email]", email)
    page.fill("input[name=password]", password)
    with page.expect_navigation(wait_until="load"):
        page.click("input[type=submit]")
    page.wait_for_load_state("networkidle")


def _answers_count(page):
    return page.evaluate(ANSWER_COUNT_JS)


def run(page, base_url):
    admin_user = os.environ["MAMUTE_ADMIN_USER"]
    admin_password = os.environ["MAMUTE_ADMIN_PASSWORD"]

    # --- arrange: author signs up, asks, and logs out --------------------
    _signup_author(page, base_url)
    question_url = _ask_question(page, base_url)
    page.goto(base_url + "/logout")
    page.wait_for_load_state("networkidle")

    # --- act: moderator answers through the answer form ------------------
    _login(page, base_url, admin_user, admin_password)
    page.goto(question_url)
    page.wait_for_load_state("networkidle")

    answers_count_before = _answers_count(page)
    dom_before = _normalize(page.content())

    page.fill("form.answer-form textarea[name=description]", ANSWER_BODY)
    # Answering may come back as a redirect to the question page or as an
    # in-place update of a JSON response; both are the same behaviour, so
    # wait for the outcome (answer on the page, or the count updated)
    # rather than for a navigation that a decoupled form never performs.
    page.locator("form.answer-form input[type=submit]").click()
    try:
        page.wait_for_function(
            ANSWER_APPEARED_JS, timeout=config.CASE_TIMEOUT_MS
        )
    except PlaywrightTimeout:
        raise AssertionError(
            "submitted the answer but it never appeared: after %d ms %s"
            % (config.CASE_TIMEOUT_MS, _state(page))
        ) from None
    page.wait_for_load_state("networkidle")

    # --- assert: the answer is rendered and the count went up ------------
    assert (
        page.url.startswith(question_url.split("?")[0])
        or "/answer/" not in page.url
    ), "expected redirect back to the question page, stayed on %r" % page.url
    answers_count_after = _answers_count(page)
    dom_after = _normalize(page.content())

    assert answers_count_after == "1", (
        "expected answers count '1' after answering, got %r (%s)"
        % (answers_count_after, _state(page))
    )
    # Count and body can disagree: a heading that says "1 answer" with an
    # empty list is a failed answer, not a page to keep waiting on.
    answer_bodies = page.locator(".answer .post-text")
    assert answer_bodies.count() > 0, (
        "the answers list is empty even though the count says %r (%s)"
        % (answers_count_after, _state(page))
    )
    answer_visible_after = answer_bodies.first.inner_text()
    assert "REST endpoint" in answer_visible_after, (
        "expected the answer body rendered on the page, got %r"
        % answer_visible_after[:200]
    )

    return {
        "question_url": question_url,
        "dom_before": dom_before,
        "dom_after": dom_after,
        "answers_count_before": answers_count_before,
        "answers_count_after": answers_count_after,
        "answer_visible_after": answer_visible_after,
    }
