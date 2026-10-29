"""E2E flow: mamute/watch-flow__watch-adds-watcher

Self-contained: signs up its own author and asks a question with the
watching checkbox UNCHECKED, so no Watcher row exists before the act.
The act under test is the watch toggle: the eye widget on the question
page POSTs /question/watched/{id} and a Watcher row is created. Asserts
the eye icon flips from not-watching to watching and returns normalized
DOM snapshots before/after the click for parity replay.

No seeded actor is needed — watching only requires a logged-in user, so
no credentials come from the environment. The arrange user is
deterministic (fixed email/password); the orchestrator resets the DB
between test dirs, so consecutive runs are identical.

Note on legacy behavior: unwatching only removes the Question_Watchers
join row (Question.remove(Watcher) mutates an in-memory list), so the
Watcher row itself persists — the watch (insert) direction is the one
with an observable DB delta, hence this behavior.
"""

import re

ARRANGE_EMAIL = "watcher@bench.test"
ARRANGE_PASSWORD = "bench-watcher-pass"
ARRANGE_NAME = "Bench Watcher"
QUESTION_TITLE = "How do I follow updates about a question I created?"
QUESTION_BODY = (
    "I created a question but I did not check the watching option. "
    "How do I start receiving updates about this question from the "
    "question page itself?"
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
    page.wait_for_selector(".select2-result-selectable", timeout=5000)
    page.click(".select2-result-selectable")
    # uncheck 'watching' so no Watcher row exists before the act — the
    # watch click is what must create it (that is the DB delta under test)
    page.uncheck("label.form-watch input[name=watching]")
    with page.expect_navigation(wait_until="load"):
        page.click("input[type=submit]")
    page.wait_for_load_state("networkidle")
    return page.url  # redirected to /{question.id}-{sluggedTitle}


def _watch_state(page):
    span = page.locator("a.watch span").first
    classes = span.get_attribute("class") or ""
    if "icon-eye-off" in classes:
        return "not-watching"
    if "icon-eye" in classes:
        return "watching"
    return "unknown"


def run(page, base_url):
    # --- arrange: author signs up and asks without watching --------------
    _signup_author(page, base_url)
    question_url = _ask_question(page, base_url)

    # --- act: click the eye widget to start watching ---------------------
    watch_state_before = _watch_state(page)
    assert watch_state_before == "not-watching", (
        "expected a fresh unwatched question, got %r" % watch_state_before
    )
    dom_before = _normalize(page.content())

    with page.expect_response("**/watched/**") as resp_info:
        page.locator("a.watch").first.click()
    assert resp_info.value.status == 200, (
        "watch POST failed with HTTP %d" % resp_info.value.status
    )
    # the click handler toggles the icon classes only after the AJAX reply
    page.wait_for_function(
        "() => {"
        "  const el = document.querySelector('a.watch span');"
        "  return el && el.classList.contains('icon-eye')"
        "         && !el.classList.contains('icon-eye-off');"
        "}",
        timeout=5000,
    )

    watch_state_after = _watch_state(page)
    dom_after = _normalize(page.content())

    assert watch_state_after == "watching", (
        "expected 'watching' after the watch click, got %r" % watch_state_after
    )

    return {
        "question_url": question_url,
        "dom_before": dom_before,
        "dom_after": dom_after,
        "watch_state_before": watch_state_before,
        "watch_state_after": watch_state_after,
    }
