import os
from playwright.sync_api import sync_playwright

def run_playwright():
    with sync_playwright() as p:
        # Launch Chromium (non-headless for now)
        browser = p.chromium.launch(
            executable_path="C:/Users/tbh2j0/AppData/Local/ms-playwright/chromium-1187/chrome.exe",
            headless=False
        )
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # Step 1: Go to Task Quicklist page
        page.goto("https://versionone.usps.gov/v1/Default.aspx?menu=TaskListPage")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        print("✅ Page loaded")

        # Step 2: Click the wrench icon (second SVG with class 'wrench')
        wrench = page.locator("svg.wrench").nth(1)
        wrench.click(timeout=5000)
        print("🔧 Wrench icon clicked")

        # Step 3: Click 'Export (.xlsx) New' from dropdown
        with page.expect_download() as download_info:
            page.locator("text=Export (.xlsx) New").click(timeout=5000)
        download = download_info.value

        # Step 4: Save the file to your target folder
        save_path = "C:/Users/tbh2j0/OneDrive - USPS/Test Folder/data/task_quicklist.xlsx"
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        print(f"📥 Downloaded file (temp): {download.path()}")
        download.save_as(save_path)
        print(f"✅ Saved to: {save_path}")

        browser.close()







