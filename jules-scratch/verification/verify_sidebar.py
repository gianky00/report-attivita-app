from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://localhost:8501")
    page.get_by_label("Matricola").fill("123")
    page.get_by_role("textbox", name="Password").fill("admin")
    page.get_by_role("button", name="Accedi").click()
    page.wait_for_load_state("networkidle")
    page.screenshot(path="jules-scratch/verification/verification.png")
    page.locator('.hamburger').click()
    page.wait_for_load_state("networkidle")
    page.screenshot(path="jules-scratch/verification/verification_collapsed.png")
    browser.close()

with sync_playwright() as playwright:
    run(playwright)
