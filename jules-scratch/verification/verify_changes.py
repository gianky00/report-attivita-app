import re
import pyotp
from playwright.sync_api import sync_playwright, expect
import time
import datetime

def run_verification(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:
        # 1. Go to the login page.
        page.goto("http://localhost:8501", timeout=90000)

        # Wait for the login form to be visible
        expect(page.get_by_text("Accesso Area Gestionale")).to_be_visible(timeout=60000)

        # --- Login and 2FA Setup ---
        # Enter matricola and password for the first time
        page.get_by_label("Matricola").fill("T001")
        page.get_by_role("textbox", name="Password").fill("password")
        page.get_by_role("button", name="Accedi").click()

        # Should be on the 2FA setup page now
        expect(page.get_by_text("Configurazione Sicurezza Account (2FA)")).to_be_visible(timeout=60000)

        # Extract the 2FA secret key
        secret_element = page.locator("code")
        expect(secret_element).to_be_visible()
        secret_key = secret_element.inner_text()

        # Generate a TOTP code
        totp = pyotp.TOTP(secret_key)
        code = totp.now()

        # Enter the code and submit
        page.get_by_label("Inserisci il codice a 6 cifre mostrato dall'app per verificare").fill(code)
        page.get_by_role("button", name="Verifica e Attiva").click()

        # Wait for the main application to load after login
        expect(page.get_by_text("Ciao, Mario Rossi!")).to_be_visible(timeout=60000)

        # --- Navigate and test the feature ---
        # 2. Go to the "Database" tab
        page.get_by_role("tab", name="Database").click()

        # 3. Click the "Ultimi 15 gg" button
        button = page.get_by_role("button", name="Ultimi 15 gg")
        expect(button).to_be_visible()
        button.click()

        # Give it a moment for the state to update and for the rerun
        page.wait_for_timeout(2000)

        # 4. Assert that the date fields are correctly populated.
        # Streamlit renders date inputs as divs with the date as value.
        today = datetime.date.today()
        fifteen_days_ago = today - datetime.timedelta(days=15)

        # Dates are in DD/MM/YYYY format
        start_date_str = fifteen_days_ago.strftime("%d/%m/%Y")
        end_date_str = today.strftime("%d/%m/%Y")

        # Find the date input widgets and check their values
        # The label is "Da:" and "A:"
        # We look for the input element associated with the label
        start_date_input = page.locator('//label[text()="Da:"]/following-sibling::div//input')
        end_date_input = page.locator('//label[text()="A:"]/following-sibling::div//input')

        expect(start_date_input).to_have_value(start_date_str)
        expect(end_date_input).to_have_value(end_date_str)

        # 5. Take a screenshot
        page.screenshot(path="jules-scratch/verification/verification.png")
        print("Verification script completed successfully and took a screenshot.")

    except Exception as e:
        print(f"An error occurred: {e}")
        page.screenshot(path="jules-scratch/verification/error.png")
    finally:
        browser.close()

with sync_playwright() as playwright:
    run_verification(playwright)