from playwright.sync_api import sync_playwright, expect

def run_verification(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:
        # Navigate to the app
        page.goto("http://localhost:8501")

        # Login
        page.get_by_label("Matricola").fill("123")
        page.get_by_role("textbox", name="Password").fill("admin")

        accedi_button = page.get_by_role("button", name="Accedi")
        accedi_button.click()

        # Wait for the login button to disappear, indicating successful login and page transition
        expect(accedi_button).to_be_hidden()

        # Now that the page has transitioned, we can safely look for the dashboard heading
        expect(page.get_by_role("heading", name="Attività Assegnate")).to_be_visible()

        # Navigate to Gestione Turni
        page.get_by_role("button", name="📅 Gestione Turni").click()

        # Wait for the target tab to be visible before clicking
        reperibilita_tab = page.get_by_role("tab", name="Turni Reperibilità")
        expect(reperibilita_tab).to_be_visible()
        reperibilita_tab.click()

        # Take a screenshot of the calendar
        page.screenshot(path="jules-scratch/verification/oncall_calendar.png")

    finally:
        browser.close()

with sync_playwright() as playwright:
    run_verification(playwright)
