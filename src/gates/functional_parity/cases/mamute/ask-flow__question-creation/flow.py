"""E2E flow: mamute/ask-flow__question-creation

Self-contained: signs up its own author, then asks a question through the
/ask form. The act under test is the question creation itself: submitting
the form must create the question and leave the user able to open its page,
which must render the title, the markdown body and the tag, with a vote
count of 0. Returns normalized DOM snapshots of the /ask form (before) and
the question page (after) for parity replay.

The submit is graded by its **outcome**, not by its transport: a
server-rendered redirect and a JSON response that updates the form page
in place are both accepted, because either way the created question has to
be reachable and render the same page.

No seeded actor is needed — question creation only requires a logged-in
user, so no credentials come from the environment. The arrange user is
deterministic (fixed email/password); the orchestrator resets the DB
between test dirs, so consecutive runs are identical.
"""

import re
import time
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError

ARRANGE_EMAIL = "asker@bench.test"
ARRANGE_PASSWORD = "bench-asker-pass"
ARRANGE_NAME = "Bench Asker"
QUESTION_TITLE = "How do I expose a legacy JSP flow through REST endpoints?"
QUESTION_BODY = (
    "Our legacy JSP pages render question data server side. "
    "We want to serve the same data from REST endpoints and render the "
    "frontend independently. What is the recommended approach?"
)
QUESTION_TAGS = "jsp"

# A link to a question is `/<id>-<slug>`; the id is numeric, so this also
# rejects the sidebar links that point at static pages.
_QUESTION_HREF = re.compile(r"^/\d+-")

# Runs in the page: report a link to a question that was not there before
# the submit, which is how a page that updates in place announces success.
_FIND_NEW_QUESTION_JS = """(seen) => {
  for (const a of document.querySelectorAll('a[href]')) {
    const path = new URL(a.href).pathname;
    if (!/^\\/\\d+-/.test(path)) continue;
    if (!seen.includes(a.href)) return a.href;
  }
  return null;
}"""


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
    dom_before = _normalize(page.content())
    seen = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
    page.fill("input[name=title]", QUESTION_TITLE)
    page.fill("textarea[name=description]", QUESTION_BODY)
    # tagNames is a select2 v3 widget (the real input is hidden); drive the UI:
    # focus -> type >= 3 chars (minimumInputLength) -> wait for the AJAX
    # result -> pick it
    page.click(".select2-container")
    page.fill(".select2-input", QUESTION_TAGS)
    page.wait_for_selector(".select2-result-selectable", timeout=5000)
    page.click(".select2-result-selectable")
    # The 'watching' checkbox is checked by default; leave it as-is so the
    # flow stays deterministic (Watcher rows are part of the DB delta).
    page.click("input[type=submit]")
    return _question_url_after_submit(page, seen), dom_before


def _question_url_after_submit(page, seen):
    """Wait for the created question, whichever way the form reported it."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if not page.url.split("?")[0].rstrip("/").endswith("/ask"):
            page.wait_for_load_state("load")
            return page.url
        try:
            found = page.evaluate(_FIND_NEW_QUESTION_JS, seen)
        except PlaywrightError:
            found = None  # mid-navigation: the loop re-checks the URL
        if found:
            page.goto(found)
            page.wait_for_load_state("networkidle")
            return page.url
        page.wait_for_timeout(250)
    raise AssertionError(
        "submitting /ask never produced a question: still on %r with no "
        "link to one" % page.url
    )


def run(page, base_url):
    # --- arrange: author signs up ----------------------------------------
    _signup_author(page, base_url)

    # --- act: create the question through the /ask form ------------------
    question_url, dom_before = _ask_question(page, base_url)

    # --- assert: the question page renders the created question ----------
    assert _QUESTION_HREF.match(urlparse(question_url).path), (
        "expected to end on the question page, got %r" % question_url
    )
    title_after = (
        page.locator(".question-title, h1").first.inner_text().strip()
    )
    assert QUESTION_TITLE in title_after, (
        "expected created question title on the page, got %r" % title_after
    )
    body_after = page.locator(".question-description").first.inner_text()
    assert "REST endpoints" in body_after, (
        "expected question body rendered on the page, got %r"
        % body_after[:200]
    )
    tag_after = page.locator(".tags-item").first.inner_text().strip()
    assert QUESTION_TAGS in tag_after, (
        "expected tag %r on the question page, got %r"
        % (QUESTION_TAGS, tag_after)
    )
    vote_count_after = (
        page.locator(".vote-container .vote-count").first.inner_text().strip()
    )
    assert vote_count_after == "0", (
        "expected vote count '0' on a fresh question, got %r"
        % vote_count_after
    )
    dom_after = _normalize(page.content())

    return {
        "question_url": question_url,
        "dom_before": dom_before,
        "dom_after": dom_after,
        "question_title": title_after,
        "question_tag": tag_after,
        "vote_count_after": vote_count_after,
    }
