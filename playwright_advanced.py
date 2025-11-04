from playwright.sync_api import sync_playwright
import os
from datetime import datetime
import pandas as pd

def run_playwright():
    with sync_playwright() as p:
        chromium_path = "C:/Users/tbh2j0/AppData/Local/ms-playwright/chromium-1187/chrome-win/chrome.exe"
        browser = p.chromium.launch(executable_path=chromium_path, headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        try:
            page.goto("https://versionone.usps.gov/v1/Default.aspx?menu=TaskListPage")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)  # Slight buffer for rendering

            # Click wrench early
            wrench = page.locator("svg.wrench").nth(1)
            wrench.click(timeout=1000)

            # Trigger export and wait for download
            with page.expect_download() as download_info:
                page.locator("text=Export (.xlsx) New").click(timeout=30000)
            download = download_info.value

            # Save the file
            save_path = "C:/Users/tbh2j0/OneDrive - USPS/Test Folder/versionone_dashboard/task_quicklist.xlsx"
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            download.save_as(save_path)

            # Optional: wait to ensure file is fully written
            page.wait_for_timeout(3000)

            with open("automation_log.txt", "a", encoding="utf-8", errors="replace") as log:
                log.write(f"[INFO] task_quicklist.xlsx saved at {datetime.now()}\n")

        except Exception as e:
            with open("automation_log.txt", "a", encoding="utf-8", errors="replace") as log:
                log.write(f"[ERROR] Playwright step failed: {str(e)}\n")

        finally:
            page.wait_for_timeout(2000)  # Final buffer before closing
            browser.close()












