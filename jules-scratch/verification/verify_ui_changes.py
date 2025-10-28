from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://localhost:8501")

    # Login
    page.get_by_label("Matricola").fill("123")
    page.get_by_role("textbox", name="Password").fill("admin")
    page.get_by_role("button", name="Accedi").click()

    # Verify 2FA
    page.wait_for_selector("text=Verifica in Due Passaggi")
    # The 2FA secret for the user created with add_admin.py is fixed, so the code is deterministic
    page.get_by_label("Ciao Admin, inserisci il codice dalla tua app di autenticazione").fill("288640")
    page.get_by_role("button", name="Verifica").click()

    # Wait for navigation to the main app
    page.wait_for_selector("text=Attività Assegnate")

    # Take a screenshot of the "Attività Assegnate" tab
    page.screenshot(path="jules-scratch/verification/verification.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
