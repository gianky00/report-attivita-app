import re
import pyotp
from playwright.sync_api import sync_playwright, expect

def run_verification(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:
        # Navigate to the app
        page.goto("http://localhost:8501")

        # --- Step 1: First Login (Password Creation) ---
        matricola = "2132"
        new_password = "testpassword123"
        page.get_by_label("Matricola").fill(matricola)
        page.get_by_role("textbox", name="Password").fill(new_password)
        page.get_by_role("button", name="Accedi").click()

        # --- Step 2: 2FA Setup ---
        expect(page.get_by_text("Configurazione Sicurezza Account (2FA)")).to_be_visible(timeout=20000)
        secret_key_element = page.locator("code")
        expect(secret_key_element).to_be_visible()
        secret_key = secret_key_element.inner_text()
        totp = pyotp.TOTP(secret_key)
        code = totp.now()
        page.get_by_label("Inserisci il codice a 6 cifre mostrato dall'app per verificare").fill(code)
        page.get_by_role("button", name="Verifica e Attiva").click()

        # --- Step 3: Main App Verification ---
        expect(page.get_by_role("heading", name=re.compile("Ciao, Giancarlo Allegretti"))).to_be_visible(timeout=30000)

        # --- Navigate to the Database tab ---
        # We target the visible text element, as the input radio button itself is not visible
        page.get_by_text("Database").click()

        # --- Verify UI Changes ---
        # 1. Assert the checkbox is GONE
        expect(page.get_by_text("Mostra solo interventi eseguiti")).not_to_be_visible()

        # 2. Assert the new info text is present
        expect(page.get_by_text("La ricerca mostra tutte le attività che hanno almeno un intervento registrato")).to_be_visible()

        # 3. Assert that some data is displayed (at least one activity expander)
        # We look for the common pattern of the expander titles
        first_activity_expander = page.locator("div[data-testid='stExpander']").first
        expect(first_activity_expander).to_be_visible()

        # Take a screenshot for visual confirmation
        page.screenshot(path="jules-scratch/verification/verification.png")
        print("Screenshot taken successfully.")

    except Exception as e:
        print(f"An error occurred: {e}")
        page.screenshot(path="jules-scratch/verification/error_screenshot.png")
        raise

    finally:
        # Clean up
        context.close()
        browser.close()

with sync_playwright() as playwright:
    run_verification(playwright)