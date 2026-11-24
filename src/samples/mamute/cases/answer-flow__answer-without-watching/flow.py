"""E2E flow: mamute/answer-flow__answer-without-watching

Self-contained: signs up its own author, asks a question, then logs in as
the seeded moderator and answers it with the form's "watch" box cleared.
Asserts the answer appears like any other; the row delta is what tells
this case apart: the moderator is not added to the question's watchers.

Moderator credentials come from the harness-injected environment only
(MAMUTE_ADMIN_USER / MAMUTE_ADMIN_PASSWORD) — never hardcoded here.
The arrange user is deterministic (fixed email/password); the orchestrator
resets the DB between test dirs, so consecutive runs are identical.
"""

import os
import re

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from settings import CASE_TIMEOUT_MS

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
        ".select2-result-selectable", timeout=CASE_TIMEOUT_MS
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


def _submit_answer(page, body):
    """Submit the answer form and wait until its outcome is on the page."""
    page.fill("form.answer-form textarea[name=description]", body)
    page.locator("form.answer-form input[type=submit]").click()
    try:
        page.wait_for_function(ANSWER_APPEARED_JS, timeout=CASE_TIMEOUT_MS)
    except PlaywrightTimeout:
        raise AssertionError(
            "submitted the answer but it never appeared: after %d ms %s"
            % (CASE_TIMEOUT_MS, _state(page))
        ) from None
    page.wait_for_load_state("networkidle")


def _alerts(page):
    """The text of every message box the page shows, in order."""
    return [
        " ".join(text.split())
        for text in page.locator(".message").all_inner_texts()
        if text.strip()
    ]


def _open(page, url):
    page.goto(url)
    page.wait_for_load_state("networkidle")


def run(page, base_url):
    admin_user = os.environ["MAMUTE_ADMIN_USER"]
    admin_password = os.environ["MAMUTE_ADMIN_PASSWORD"]

    # --- arrange: author asks; moderator opens the question --------------
    _signup_author(page, base_url)
    question_url = _ask_question(page, base_url)
    _open(page, base_url + "/logout")
    _login(page, base_url, admin_user, admin_password)
    _open(page, question_url)
    answers_count_before = _answers_count(page)
    dom_before = _normalize(page.content())

    # --- act: answer with the watch box cleared --------------------------
    watch = page.locator("form.answer-form input[name=watching]")
    watch.uncheck()
    assert not watch.is_checked(), "the watch box must be cleared"
    _submit_answer(page, ANSWER_BODY)

    # --- assert: the answer is on the page -------------------------------
    answers_count_after = _answers_count(page)
    dom_after = _normalize(page.content())
    assert answers_count_after == "1", _state(page)
    answer_visible_after = page.locator(".answer .post-text").first
    answer_visible_after = answer_visible_after.inner_text()
    assert "REST endpoint" in answer_visible_after, answer_visible_after

    return {
        "question_url": question_url,
        "dom_before": dom_before,
        "dom_after": dom_after,
        "answers_count_before": answers_count_before,
        "answers_count_after": answers_count_after,
        "answer_visible_after": answer_visible_after,
    }
