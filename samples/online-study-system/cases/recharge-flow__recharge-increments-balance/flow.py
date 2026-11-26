"""E2E flow: online-study-system/recharge-flow__recharge-increments-balance

The seeded student 小明 (balance 80) recharges the account with the 100
denomination on the recharge page.  The stored balance must go 80 -> 180
and the page must show the new value.

Note: the recharge page has no menu link in this legacy app (dead UI link)
— the flow navigates to /student/recharge directly, which is the route the
page is served at.

Credentials come from the harness-injected environment only
(OSS_STUDENT_USER / OSS_STUDENT_PASSWORD) — never hardcoded here.
"""

import os
import re


def _normalize(html):
    html = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<style\b.*?</style>", "", html, flags=re.S | re.I)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def _goto(page, url):
    try:
        page.goto(url, wait_until="load")
    except Exception:
        page.goto(url, wait_until="load")
    page.wait_for_load_state("networkidle")


def _login(page, base_url):
    user = os.environ["OSS_STUDENT_USER"]
    password = os.environ["OSS_STUDENT_PASSWORD"]
    _goto(page, base_url + "/login")
    page.fill("input[name=name]", user)
    page.fill("input[name=password]", password)
    with page.expect_navigation(wait_until="load"):
        page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")


def run(page, base_url):
    _login(page, base_url)

    _goto(page, base_url + "/student/recharge")
    balance_before = page.input_value("input[name=balance]").strip()
    dom_before = _normalize(page.content())
    assert balance_before == "80", (
        "expected seeded balance '80', got %r" % balance_before
    )

    # --- act: pick the 100 denomination and submit -------------------------
    page.check("input[name=money][value='100']")
    with page.expect_response("**/student/updateBalance") as resp_info:
        page.click("button[form=rechargeForm]")
    assert resp_info.value.status == 200, (
        "recharge POST failed with HTTP %d" % resp_info.value.status
    )
    page.wait_for_load_state("networkidle")

    page.wait_for_function(
        "() => document.querySelector('input[name=balance]').value !== '%s'"
        % balance_before,
        timeout=5000,
    )
    balance_after = page.input_value("input[name=balance]").strip()
    dom_after = _normalize(page.content())

    assert balance_after == "180", (
        "expected balance '180' after recharging 100, got %r" % balance_after
    )

    return {
        "balance_before": balance_before,
        "balance_after": balance_after,
        "dom_before": dom_before,
        "dom_after": dom_after,
    }
