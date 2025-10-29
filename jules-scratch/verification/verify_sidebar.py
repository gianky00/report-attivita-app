
from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    page.goto("http://localhost:8515")

    page.get_by_label("Matricola").fill("123")
    page.get_by_role('textbox', name='Password').fill("admin")
    page.get_by_role("button", name="Accedi").click()
    page.wait_for_load_state("networkidle")

    page.screenshot(path="jules-scratch/verification/dashboard.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
