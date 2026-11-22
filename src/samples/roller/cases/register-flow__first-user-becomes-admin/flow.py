"""E2E flow: roller/register-flow__first-user-becomes-admin

On a fresh schema the front page is Roller's setup page, which links to the
registration form. The flow registers the first account there; Roller makes
that account the site administrator and shows its welcome page.

Credentials come from the sample's environment only
(ROLLER_ADMIN_USER / ROLLER_ADMIN_PASSWORD) — never hardcoded here.
"""

import os
import re


def _goto(page, url):
    page.goto(url, wait_until="load")
    page.wait_for_load_state("networkidle")


def _type(page, selector, value):
    # The form's onChange() runs on keyup and is what enables the submit
    # button, so the value is typed, not filled.
    page.fill(selector, "")
    page.locator(selector).press_sequentially(value)


def _heading(page):
    return re.sub(r"\s+", " ", page.locator("h1, h2").first.inner_text()).strip()


def run(page, base_url):
    user = os.environ["ROLLER_ADMIN_USER"]
    password = os.environ["ROLLER_ADMIN_PASSWORD"]

    _goto(page, base_url + "/")
    setup_heading = _heading(page)
    link = page.locator("a#a_createUser")
    assert link.count() == 1, (
        "no create-user link on a fresh site; page at %s says: %s"
        % (page.url, setup_heading)
    )

    # --- act: register the first account -----------------------------------
    with page.expect_navigation(wait_until="load"):
        link.click()
    page.wait_for_load_state("networkidle")
    assert "register" in page.url, "expected the register form, got %s" % page.url
    register_heading = _heading(page)

    _type(page, "input[name='bean.userName']", user)
    _type(page, "input[name='bean.screenName']", "Site Admin")
    _type(page, "input[name='bean.fullName']", "Site Administrator")
    _type(page, "input[name='bean.emailAddress']", "admin@example.com")
    _type(page, "input[name='bean.passwordText']", password)
    _type(page, "input[name='bean.passwordConfirm']", password)
    page.select_option("select[name='bean.locale']", value="en_US")
    page.select_option("select[name='bean.timeZone']", value="UTC")
    assert page.locator("#submit").is_enabled(), (
        "the register button stayed disabled after filling the form"
    )
    with page.expect_navigation(wait_until="load"):
        page.click("#submit")
    page.wait_for_load_state("networkidle")

    errors = page.locator(".errors")
    assert errors.count() == 0, (
        "registration refused at %s: %s" % (page.url, errors.first.inner_text())
    )
    login_link = page.locator("a#a_clickHere")
    assert login_link.count() == 1, (
        "no welcome page after registering; page at %s says: %s"
        % (page.url, page.locator("body").inner_text()[:400])
    )
    account_created = re.sub(
        r"\s+", " ", page.locator("p").first.inner_text()
    ).strip()

    return {
        "setup_heading": setup_heading,
        "register_heading": register_heading,
        "account_created": account_created,
    }
