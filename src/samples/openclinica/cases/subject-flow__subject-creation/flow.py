"""E2E flow: openclinica/subject-flow__subject-creation

Self-contained: logs in as the seeded admin (credentials from the
harness-injected environment only — openclinica has no in-flow signup),
opens the AddNewSubject form and enrolls a subject with fixed data. The
act under test is the subject creation: submitting the form must land on
the study-subject list with the new Study Subject ID visible. Returns
normalized DOM snapshots of the form (before) and the list page (after)
for parity replay.

Dates are filled explicitly (the form prefills enrollmentDate with
*today*, which would break determinism otherwise).

The app stalls on keep-alive reuse: a page's images can stay "pending"
forever on a reused connection, so the browser's `load` event never fires.
Every navigation therefore waits for `domcontentloaded` (the markup and its
scripts are in place; the two login-page images are cosmetic), and `_goto`
retries once in case the main document itself is the stalled one. Each case
gets its own fresh stack, so consecutive runs are identical.
"""

import os
import re

from settings import CASE_TIMEOUT_MS

SUBJECT_LABEL = "SUBJ-BENCH-001"
PERSON_ID = "PERSON-BENCH-001"
ENROLLMENT_DATE = "01-Jan-2026"
DATE_OF_BIRTH = "15-Mar-1990"
GENDER = "m"


def _normalize(html):
    """Strip volatile markup so two runs of this flow are identical."""
    html = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<style\b.*?</style>", "", html, flags=re.S | re.I)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def _goto(page, url):
    """goto with one retry, never waiting for the stalled subresources."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=CASE_TIMEOUT_MS)
    except Exception:
        page.goto(url, wait_until="domcontentloaded", timeout=CASE_TIMEOUT_MS)
    page.wait_for_load_state("domcontentloaded")


def _login(page, base_url):
    _goto(page, base_url + "/")
    page.fill("#username", os.environ["OPENCLINICA_ADMIN_USER"])
    page.fill("#j_password", os.environ["OPENCLINICA_ADMIN_PASSWORD"])
    with page.expect_navigation(
        wait_until="domcontentloaded", timeout=CASE_TIMEOUT_MS
    ):
        page.click("input.loginbutton")
    page.wait_for_load_state("domcontentloaded")


def run(page, base_url):
    # --- arrange: log in as the seeded admin -----------------------------
    _login(page, base_url)

    # --- act: enroll a subject through the AddNewSubject form ------------
    _goto(page, base_url + "/AddNewSubject")
    dom_before = _normalize(page.content())
    page.fill("input[name=label]", SUBJECT_LABEL)
    page.fill("input[name=uniqueIdentifier]", PERSON_ID)
    page.fill("input[name=enrollmentDate]", ENROLLMENT_DATE)
    page.select_option("select[name=gender]", GENDER)
    page.fill("input[name=dob]", DATE_OF_BIRTH)
    with page.expect_navigation(
        wait_until="domcontentloaded", timeout=CASE_TIMEOUT_MS
    ):
        page.click("input[name=submitDone]")
    page.wait_for_load_state("domcontentloaded")

    # --- assert: the subject list shows the new subject ------------------
    subject_url = page.url
    subject_visible_after = page.locator(f"text={SUBJECT_LABEL}").count() > 0
    dom_after = _normalize(page.content())

    assert subject_visible_after, (
        "expected %r on the study-subject list after creation" % SUBJECT_LABEL
    )

    return {
        "subject_url": subject_url,
        "dom_before": dom_before,
        "dom_after": dom_after,
        "subject_label": SUBJECT_LABEL,
        "subject_visible_after": subject_visible_after,
    }
