"""E2E flow: bookshopweb/category-flow__create-category-inserts-row

The seeded admin signs in to the admin console, opens the create-category
form from the category list, and submits a name and a description without
an image. The app must insert the category row, re-render the form with its
success message, and list the new category in the category manager.

Credentials come from the sample's environment only
(BSW_ADMIN_USER / BSW_ADMIN_PASSWORD) — never hardcoded here.
"""

import os
import re

CATEGORY_NAME = "Sách thử nghiệm"
CATEGORY_DESCRIPTION = "Danh mục tạo bởi kịch bản kiểm tra."


def _normalize(html):
    html = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<style\b.*?</style>", "", html, flags=re.S | re.I)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def _goto(page, url):
    page.goto(url, wait_until="load")
    page.wait_for_load_state("networkidle")


def _signin(page, base_url):
    _goto(page, base_url + "/admin/signin")
    page.fill("input[name=username]", os.environ["BSW_ADMIN_USER"])
    page.fill("input[name=password]", os.environ["BSW_ADMIN_PASSWORD"])
    with page.expect_navigation(wait_until="load"):
        page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    assert re.search(r"/admin/?$", page.url), (
        "admin sign-in did not land on /admin, got %s" % page.url
    )


def run(page, base_url):
    _signin(page, base_url)

    _goto(page, base_url + "/admin/categoryManager")
    listing_before = _normalize(page.content())
    assert CATEGORY_NAME not in listing_before, (
        "category %r must not exist before the create" % CATEGORY_NAME
    )

    # --- act: open the form, fill it, submit -------------------------------
    _goto(page, base_url + "/admin/categoryManager/create")
    form_heading = page.locator("h3.section-title").first.inner_text().strip()
    page.fill("input[name=name]", CATEGORY_NAME)
    page.fill("textarea[name=description]", CATEGORY_DESCRIPTION)
    with page.expect_navigation(wait_until="load"):
        page.click("form button[type=submit]")
    page.wait_for_load_state("networkidle")

    alert = page.locator(".alert-success")
    assert alert.count() == 1, (
        "no success message after submit; page at %s says: %s"
        % (page.url, page.locator("body").inner_text()[:400])
    )
    success_message = alert.first.inner_text().strip()

    # --- after: the category manager lists it ------------------------------
    _goto(page, base_url + "/admin/categoryManager")
    row = page.locator("tr", has_text=CATEGORY_NAME)
    assert row.count() == 1, (
        "category %r missing from the category manager" % CATEGORY_NAME
    )
    new_category_row = re.sub(r"\s+", " ", row.first.inner_text()).strip()

    return {
        "form_heading": form_heading,
        "success_message": success_message,
        "new_category_row": new_category_row,
    }
