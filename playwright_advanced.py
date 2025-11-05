from playwright.sync_api import sync_playwright
import os
from datetime import datetime
import pandas as pd

DOWNLOAD_DIR = "C:/Users/tbh2j0/OneDrive - USPS/Test Folder/versionone_dashboard"
FINAL_OUTPUT = os.path.join(DOWNLOAD_DIR, "task_quicklist.csv")
CHROMIUM_PATH = "C:/Users/tbh2j0/AppData/Local/ms-playwright/chromium-1187/chrome-win/chrome.exe"
V1_URL = "https://versionone.usps.gov/v1/Default.aspx?menu=TaskListPage"

PLANNING_LEVELS = [
    "EDS-4834",
    "EEB-9372",
    "UAP-IV-9443",
    "UAPSAL-9402",
    "UAP-SPM-9442"
]

def run_playwright():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM_PATH, headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        all_files = []

        page.goto(V1_URL)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)

        # Step 1: Export CDAS-6441 (default view)
        try:
            print("[INFO] Exporting CDAS-6441")
            wrench = page.locator("svg.wrench").nth(1)
            wrench.wait_for(state="visible", timeout=10000)
            wrench.click(timeout=3000)
            page.wait_for_timeout(1500)

            export_btn = page.locator("text=Export (.xlsx) New")
            export_btn.wait_for(state="visible", timeout=5000)
            with page.expect_download(timeout=30000) as download_info:
                export_btn.click()
            download = download_info.value

            filename = "tasklist_CDAS6441.xlsx"
            save_path = os.path.join(DOWNLOAD_DIR, filename)
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            download.save_as(save_path)
            all_files.append(save_path)

            print(f"[SUCCESS] {filename} saved")
            page.wait_for_timeout(5000)

        except Exception as e:
            print(f"[ERROR] Failed to export CDAS-6441: {str(e)}")

        # Step 2: Loop through remaining planning levels
        for pl in PLANNING_LEVELS:
            try:
                print(f"\n[INFO] Selecting planning level: {pl}")

                # Open dropdown
                page.locator(".new-project-selector").click(force=True)
                page.wait_for_timeout(2000)

                # Find and click the planning level
                matches = page.locator(f"text={pl}").all()
                match_count = len(matches)
                print(f"[DEBUG] Found {match_count} matches for {pl}")

                if match_count == 0:
                    raise Exception(f"No matching elements found for {pl}")

                selected = False
                for i, match in enumerate(matches):
                    try:
                        match.scroll_into_view_if_needed()
                        match.click(force=True)
                        page.wait_for_timeout(2000)
                        print(f"[INFO] Clicked match #{i+1} for {pl}")
                        selected = True
                        break
                    except Exception as e:
                        print(f"[WARN] Match #{i+1} failed: {e}")

                if not selected:
                    raise Exception(f"Failed to select {pl} after trying all matches")

                # DON'T close dropdown - Apply button is inside it
                # Click Apply button while dropdown is still open
                print("[INFO] Attempting to click Apply button (inside dropdown)")

                apply_selectors = [
                    "button.MuiButton-root:has-text('Apply')",
                    "button:has(span:text('Apply'))",
                    "button.MuiButtonBase-root:has-text('Apply')",
                    "button >> text=Apply",
                    ".action-buttons button:has-text('Apply')",
                    "#PlanningLevelFilters button:has-text('Apply')"
                ]

                clicked = False
                for selector in apply_selectors:
                    try:
                        apply_btn = page.locator(selector).first
                        apply_btn.wait_for(state="visible", timeout=3000)
                        apply_btn.scroll_into_view_if_needed()
                        page.wait_for_timeout(500)
                        apply_btn.click(force=True)
                        print(f"[SUCCESS] Clicked Apply using selector: {selector}")
                        clicked = True
                        break
                    except Exception as e:
                        print(f"[DEBUG] Selector '{selector}' failed: {e}")

                if not clicked:
                    print("[WARN] All selectors failed, taking screenshot")
                    page.screenshot(path=f"apply_button_debug_{pl}.png")
                    raise Exception("Failed to click Apply button with all selectors")

                # Wait for page to reload
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(5000)

                # Export the report
                print(f"[INFO] Exporting report for {pl}")
                wrench = page.locator("svg.wrench").nth(1)
                wrench.wait_for(state="visible", timeout=10000)
                wrench.click(timeout=3000)
                page.wait_for_timeout(1500)

                export_btn = page.locator("text=Export (.xlsx) New")
                export_btn.wait_for(state="visible", timeout=5000)
                with page.expect_download(timeout=30000) as download_info:
                    export_btn.click()
                download = download_info.value

                tag = pl.replace(" ", "").replace("-", "")
                filename = f"tasklist_{tag}.xlsx"
                save_path = os.path.join(DOWNLOAD_DIR, filename)
                download.save_as(save_path)
                all_files.append(save_path)

                print(f"[SUCCESS] {filename} saved")
                page.wait_for_timeout(3000)

            except Exception as e:
                print(f"[ERROR] Failed for {pl}: {str(e)}")
                try:
                    page.screenshot(path=f"error_{pl}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                except:
                    pass

        # Step 3: Reset back to CDAS-6441
        try:
            print("\n[INFO] Resetting to CDAS-6441")
            page.locator(".new-project-selector").click(force=True)
            page.wait_for_timeout(2000)

            cdas_matches = page.locator("text=CDAS-6441").all()
            if cdas_matches:
                cdas_matches[0].scroll_into_view_if_needed()
                cdas_matches[0].click(force=True)
                page.wait_for_timeout(2000)

                # Click Apply to confirm selection
                apply_selectors = [
                    "button.MuiButton-root:has-text('Apply')",
                    "button:has(span:text('Apply'))",
                    "button >> text=Apply"
                ]
                for selector in apply_selectors:
                    try:
                        page.locator(selector).first.click(force=True)
                        print("[SUCCESS] Reset to CDAS-6441")
                        break
                    except:
                        continue

                page.wait_for_timeout(2000)
        except Exception as e:
            print(f"[WARN] Could not reset to CDAS-6441: {e}")

        browser.close()
        merge_tasklists(all_files)

def merge_tasklists(file_paths):
    dfs = []
    for f in file_paths:
        try:
            df = pd.read_excel(f)
            df["Planning Level"] = os.path.basename(f).split("_")[1].replace(".xlsx", "")
            dfs.append(df)
        except Exception as e:
            print(f"[ERROR] Failed to read {f}: {str(e)}")

    if dfs:
        tasklist_df = pd.concat(dfs, ignore_index=True)
        tasklist_df.to_csv(FINAL_OUTPUT, index=False)
        print(f"[SUCCESS] Combined CSV saved to {FINAL_OUTPUT}")
    else:
        print("[ERROR] No files to merge")

if __name__ == "__main__":
    run_playwright()


