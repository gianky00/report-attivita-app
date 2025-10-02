from playwright.sync_api import sync_playwright, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:
        # The Streamlit app is running on the default port 8501
        page.goto("http://localhost:8501")

        # Wait for the title to be "Login" to ensure the page has loaded
        expect(page).to_have_title("Login", timeout=10000)

        # Take a screenshot of the login page
        page.screenshot(path="jules-scratch/verification/verification.png")
        print("Screenshot taken successfully.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        browser.close()

with sync_playwright() as playwright:
    run(playwright)