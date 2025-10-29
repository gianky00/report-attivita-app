
from playwright.sync_api import sync_playwright, expect

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto("http://localhost:8517")

            # Login
            page.get_by_label("Matricola").fill("admin")
            page.get_by_role("textbox", name="Password").fill("admin")
            page.get_by_role("button", name="Accedi").click()

            # Use a robust wait strategy for the dashboard title
            dashboard_title = page.locator('h1:has-text("Attività Assegnate")')

            # The expect function has a built-in wait. This is much more reliable.
            expect(dashboard_title).to_be_visible(timeout=10000)

            print("Successfully logged in and found dashboard title.")

            # Take screenshot
            page.screenshot(path="jules-scratch/verification/dashboard.png")
            print("Screenshot saved to jules-scratch/verification/dashboard.png")

        except Exception as e:
            print(f"An error occurred: {e}")
            page.screenshot(path="jules-scratch/verification/error.png")
        finally:
            browser.close()

if __name__ == "__main__":
    run_verification()
