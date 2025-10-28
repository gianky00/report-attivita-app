
from playwright.sync_api import Page, expect

def test_login_page(page: Page):
    try:
        print("Navigating to the application...")
        page.goto("http://localhost:8501", timeout=60000)
        print("Page loaded. Taking screenshot...")
        page.screenshot(path="jules-scratch/verification/login_page.png")
        print("Screenshot of login page saved.")
    except Exception as e:
        print(f"An error occurred: {e}")
