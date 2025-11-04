from playwright.sync_api import sync_playwright
import os
from datetime import datetime

def run_playwright():
    with sync_playwright() as p:
        # Manually specify the path to your headless shell
        chromium_path = "C:/Users/tbh2j0/AppData/Local/ms-playwright/chromium-1187/chrome-win/chrome.exe"

        browser = p.chromium.launch(executable_path=chromium_path, headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        try:
            page.goto("https://versionone.usps.gov/v1/Default.aspx?menu=TaskListPage")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)

            wrench = page.locator("svg.wrench").nth(1)
            wrench.click(timeout=5000)

            with page.expect_download() as download_info:
                page.locator("text=Export (.xlsx) New").click(timeout=5000)
            download = download_info.value

            save_path = "C:/Users/tbh2j0/OneDrive - USPS/Test Folder/versionone_dashboard/task_quicklist.xlsx"
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            download.save_as(save_path)

            with open("automation_log.txt", "a", encoding="utf-8", errors="replace") as log:
                log.write(f"[INFO] task_quicklist.xlsx saved at {datetime.now()}\n")

        except Exception as e:
            with open("automation_log.txt", "a", encoding="utf-8", errors="replace") as log:
                log.write(f"[ERROR] Playwright step failed: {str(e)}\n")

        finally:
            browser.close()











