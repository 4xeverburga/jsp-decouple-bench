"""E2E flow: openclinica/subject-flow__invalid-fields-refused

One submission with every field wrong in its own way: markup in the
study subject, secondary and person IDs, a secondary ID longer than 30
characters, a date of birth that is not a date, an enrollment date in the
future (2099, fixed so the case stays deterministic) and no gender. Each
check adds its own message; the page shows them all, and nothing is
written.

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

    # --- act: every field invalid at once ---------------------------------
    dom_before = _add(
        page,
        base_url,
        {
            "label": "<SUBJ-BENCH-001>",
            "uniqueIdentifier": "<PERSON-BENCH-001>",
            "secondaryLabel": "<" + "S" * 30 + ">",
            "enrollmentDate": "01-Jan-2099",
            "gender": "",
            "dob": "not-a-date",
        },
        DONE,
    )

    # --- assert: refused, the form is shown again with the reasons -------
    alerts_after = _alerts(page)
    dom_after = _normalize(page.content())
    assert page.locator("input[name=label]").count() == 1, (
        "a refused add must show the form again, got %s" % page.url
    )
    assert alerts_after, "the refusal must say why"
    dom_list = _listed(page, base_url)

    return {
        "dom_before": dom_before,
        "dom_after": dom_after,
        "dom_list": dom_list,
        "alerts_after": alerts_after,
    }
