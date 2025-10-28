
import re
import traceback
from playwright.sync_api import Page, expect, TimeoutError

def test_storico_page(page: Page):
    try:
        print("Navigating to the application...")
        page.goto("http://localhost:8501")

        print("Logging in...")
        page.get_by_label("Username").fill("admin")
        page.get_by_label("Password").fill("admin")
        page.get_by_role("button", name="Login").click()

        print("Waiting for the overview page to load...")
        expect(page).to_have_url(re.compile(".*overview"), timeout=10000)
        print("Overview page loaded.")

        print("Navigating to the 'Storico' page...")
        page.get_by_role("link", name="Storico").click()
        expect(page).to_have_url(re.compile(".*storico"), timeout=10000)
        print("'Storico' page loaded.")

        print("Clicking the 'Storico Attività' tab...")
        page.get_by_role("tab", name="Storico Attività").click()

        print("Waiting for the first PDL expander to be visible...")
        first_expander = page.locator(".st-expander").first
        expect(first_expander).to_be_visible(timeout=10000)
        print("First PDL expander is visible. Clicking it...")
        first_expander.click()

        print("Waiting for the first intervention expander to be visible...")
        first_inner_expander = page.locator(".st-expander .st-expander").first
        expect(first_inner_expander).to_be_visible(timeout=10000)
        print("First intervention expander is visible. Clicking it...")
        first_inner_expander.click()

        print("Taking screenshot...")
        page.screenshot(path="jules-scratch/verification/verification.png")
        print("Screenshot saved to jules-scratch/verification/verification.png")

    except TimeoutError as e:
        print(f"A timeout error occurred: {e}")
        print(traceback.format_exc())
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        print(traceback.format_exc())
