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
            page.wait_for_timeout(1000)

            wrench = page.locator("svg.wrench").nth(1)
            wrench.click(timeout=5000)

            with page.expect_download() as download_info:
                page.locator("text=Export (.xlsx) New").click(timeout=5000)
            download = download_info.value

            save_path = "C:/Users/tbh2j0/OneDrive - USPS/Test Folder/versionone_dashboard/task_quicklist.xlsx"
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            download.save_as(save_path)

            # ✅ Consolidate into master file
            archive_path = "C:/Users/tbh2j0/OneDrive - USPS/Test Folder/versionone_dashboard/task_quicklist_master.xlsx"
            new_df = pd.read_excel(save_path)
            new_df["Imported On"] = pd.Timestamp.now()

            if os.path.exists(archive_path):
                old_df = pd.read_excel(archive_path)
                combined_df = pd.concat([old_df, new_df], ignore_index=True)
                combined_df.drop_duplicates(subset=["ID"], keep="last", inplace=True)
            else:
                combined_df = new_df

            combined_df.to_excel(archive_path, index=False)

            with open("automation_log.txt", "a", encoding="utf-8", errors="replace") as log:
                log.write(f"[INFO] task_quicklist.xlsx saved and master file updated with {len(new_df)} new rows at {datetime.now()}\n")

        except Exception as e:
            with open("automation_log.txt", "a", encoding="utf-8", errors="replace") as log:
                log.write(f"[ERROR] Playwright step failed: {str(e)}\n")

        finally:
            browser.close()












