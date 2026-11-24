"""E2E flow: openclinica/subject-flow__save-and-assign-event

Enrolls a subject with "Save and Assign Study Event": the subject is
saved and the app moves on to scheduling an event for it, with the new
subject already chosen. No event is scheduled. Then opens the list.

Single actor: the seeded admin (credentials from the harness-injected
environment only). Dates are filled explicitly; each case gets its own
fresh stack, so consecutive runs are identical. Navigation waits for
`domcontentloaded` (see subject-flow__subject-creation for why).
"""

import os
import re

from settings import CASE_TIMEOUT_MS

SUBJECT_LABEL = "SUBJ-BENCH-001"
PERSON_ID = "PERSON-BENCH-001"
ENROLLMENT_DATE = "01-Jan-2026"
DATE_OF_BIRTH = "15-Mar-1990"
GENDER = "m"
DONE = "input[name=submitDone]"


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


def _add(page, base_url, fields, button):
    """Fill the AddNewSubject form with `fields` and press `button`."""
    _goto(page, base_url + "/AddNewSubject")
    dom_form = _normalize(page.content())
    for name, value in fields.items():
        if name == "gender":
            page.select_option("select[name=gender]", value)
        else:
            page.fill("input[name=%s]" % name, value)
    with page.expect_navigation(
        wait_until="domcontentloaded", timeout=CASE_TIMEOUT_MS
    ):
        page.click(button)
    page.wait_for_load_state("domcontentloaded")
    return dom_form


def _subject(label, person):
    return {
        "label": label,
        "uniqueIdentifier": person,
        "enrollmentDate": ENROLLMENT_DATE,
        "gender": GENDER,
        "dob": DATE_OF_BIRTH,
    }


def _alerts(page):
    """Every message the page shows, page-level and per field."""
    return [
        " ".join(text.split())
        for text in page.locator(".alert").all_inner_texts()
        if text.strip()
    ]


def _listed(page, base_url):
    _goto(page, base_url + "/ListStudySubjects")
    return _normalize(page.content())


def run(page, base_url):
    _login(page, base_url)

    # --- act: enroll with "Save and Assign Study Event" ------------------
    dom_before = _add(
        page,
        base_url,
        _subject(SUBJECT_LABEL, PERSON_ID),
        "input[name=submitEvent]",
    )

    # --- assert: the event page, for the new subject ---------------------
    alerts_after = _alerts(page)
    dom_after = _normalize(page.content())
    assert page.locator("text=" + SUBJECT_LABEL).count() > 0, (
        "the event page must name the new subject, got %s" % page.url
    )

    # --- assert: the list shows the subject ------------------------------
    dom_list = _listed(page, base_url)
    assert page.locator("text=" + SUBJECT_LABEL).count() > 0, (
        "expected %r on the study-subject list" % SUBJECT_LABEL
    )

    return {
        "dom_before": dom_before,
        "dom_after": dom_after,
        "dom_list": dom_list,
        "alerts_after": alerts_after,
    }
