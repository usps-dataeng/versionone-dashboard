from playwright.sync_api import sync_playwright
import os
from datetime import datetime
import pandas as pd



DOWNLOAD_DIR = "C:/Users/tbh2j0/OneDrive - USPS/Test Folder/versionone_dashboard"
FINAL_OUTPUT = os.path.join(DOWNLOAD_DIR, "task_quicklist.xlsx")
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
        browser = p.chromium.launch(executable_path=CHROMIUM_PATH, headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        all_files = []

        page.goto(V1_URL)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)

        # Dismiss any banner notifications that might block the UI
        try:
            print("[INFO] Checking for banner notifications to dismiss")
            dismiss_btn = page.locator("button:has-text('Dismiss')")
            if dismiss_btn.is_visible(timeout=3000):
                dismiss_btn.click()
                print("[SUCCESS] Dismissed banner notification")
                page.wait_for_timeout(1000)
        except Exception as e:
            print(f"[INFO] No banner to dismiss or already dismissed: {str(e)}")

        # Step 1: Export CDAS - 6441 (default view)
        try:
            print("[INFO] Exporting CDAS - 6441")
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
            print(f"[ERROR] Failed to export CDAS - 6441: {str(e)}")

        # Step 2: Loop through remaining planning levels
        for pl in PLANNING_LEVELS:
            try:
                print(f"\n[INFO] Selecting planning level: {pl}")

                # Ensure any open modals are closed
                try:
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(500)
                except:
                    pass

                # Open dropdown
                dropdown = page.locator(".new-project-selector")
                dropdown.wait_for(state="visible", timeout=10000)
                dropdown.click(force=True)
                page.wait_for_timeout(2000)

                # Find and click the planning level
                max_attempts = 5
                matches = []
                for attempt in range(max_attempts):
                    matches = page.locator(f"text={pl}").all()
                    if matches:
                        break
                    print(f"[DEBUG] Attempt {attempt+1}: no matches for {pl}")
                    page.wait_for_timeout(1000)

                match_count = len(matches)
                print(f"[DEBUG] Found {match_count} matches for {pl}")


                if match_count == 0:
                    raise Exception(f"No matching elements found for {pl}")

                # Try each match until we find one that shows the Apply button
                selected = False
                apply_selectors = [
                    "button.MuiButton-root:has-text('Apply')",
                    "button:has(span:text('Apply'))",
                    "button.MuiButtonBase-root:has-text('Apply')",
                    "button >> text=Apply",
                    ".action-buttons button:has-text('Apply')",
                    "#PlanningLevelFilters button:has-text('Apply')"
                ]

                for i, match in enumerate(matches):
                    try:
                        print(f"[DEBUG] Trying match #{i+1}/{match_count} for {pl}")
                        match.scroll_into_view_if_needed()
                        match.click(force=True)
                        page.wait_for_timeout(1500)

                        # Check if Apply button appears after clicking this match
                        apply_visible = False
                        for selector in apply_selectors:
                            try:
                                apply_btn = page.locator(selector).first
                                apply_btn.wait_for(state="visible", timeout=1000)
                                apply_visible = True
                                print(f"[SUCCESS] Match #{i+1} shows Apply button")
                                break
                            except:
                                continue

                        if apply_visible:
                            selected = True
                            break
                        else:
                            print(f"[DEBUG] Match #{i+1} did not show Apply button, trying next")

                    except Exception as e:
                        print(f"[DEBUG] Failed to click match #{i+1}: {str(e)}")

                if not selected:
                    print("[WARN] No match showed Apply button, taking screenshot")
                    page.screenshot(path=f"no_apply_button_{pl}.png")
                    raise Exception(f"No valid match found for {pl}")

                # Click Apply button
                print("[INFO] Clicking Apply button")
                clicked = False
                for selector in apply_selectors:
                    try:
                        apply_btn = page.locator(selector).first
                        apply_btn.wait_for(state="visible", timeout=3000)
                        apply_btn.scroll_into_view_if_needed()
                        page.wait_for_timeout(500)
                        apply_btn.click(force=True)
                        print(f"[SUCCESS] Applied using selector: {selector}")
                        clicked = True
                        break
                    except Exception as e:
                        print(f"[DEBUG] Selector '{selector}' failed: {e}")

                if not clicked:
                    print("[WARN] Apply button click failed, taking screenshot")
                    page.screenshot(path=f"apply_button_debug_{pl}.png")
                    raise Exception("Failed to click Apply button")

                # Wait for the selector modal to close
                print("[INFO] Waiting for modal to close...")
                try:
                    page.wait_for_selector("div.selector-modal", state="hidden", timeout=10000)
                    print("[SUCCESS] Modal closed")
                except:
                    print("[WARN] Modal close timeout, continuing anyway")

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

                # Try to recover by closing any open modals/menus
                try:
                    print("[INFO] Attempting to recover from error...")
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1000)
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1000)
                except:
                    pass

        # Step 3: Reset back to CDAS-6441
        try:
            print("\n[INFO] Resetting to CDAS - 6441")

            # Open dropdown
            page.locator(".new-project-selector").click(force=True)
            page.wait_for_timeout(2000)

            cdas_matches = page.locator("text=CDAS - 6441").all()
            match_count = len(cdas_matches)
            print(f"[DEBUG] Found {match_count} matches for CDAS - 6441")

            selected = False
            for i, match in enumerate(cdas_matches):
                try:
                    match.scroll_into_view_if_needed()
                    match.click(force=True)
                    page.wait_for_timeout(2000)
                    print(f"[INFO] Clicked CDAS - 6441 match #{i+1}")
                    selected = True
                    break
                except Exception as e:
                    print(f"[WARN] CDAS - 6441 match #{i+1} failed: {e}")

            # DON'T close dropdown - Apply button is inside it
            if selected:
                # Click Apply to confirm selection (dropdown is still open)
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
                        print(f"[SUCCESS] Reset to CDAS - 6441 using selector: {selector}")
                        clicked = True
                        break
                    except Exception as e:
                        print(f"[DEBUG] Apply selector '{selector}' failed: {e}")

                if clicked:
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(3000)
            else:
                print("[WARN] Could not select CDAS - 6441")

        except Exception as e:
            print(f"[ERROR] Failed to reset to CDAS - 6441: {e}")
            try:
                page.screenshot(path=f"error_reset_cdas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            except:
                pass

        browser.close()
        merge_tasklists(all_files)

def merge_tasklists(file_paths):
    dfs = []
    for f in file_paths:
        try:
            df = pd.read_excel(f)
            print(f"\n[DEBUG] Processing: {f}")
            print(f"[DEBUG] Rows in file: {len(df)}")

            # Compute Completed Hours using Est. Hours and To Do
            if "Est. Hours" in df.columns and "To Do" in df.columns:
                df["Completed Hours"] = df["Est. Hours"] - df["To Do"]
                total_completed = df["Completed Hours"].sum()
                total_est = df["Est. Hours"].sum()
                print(f"[DEBUG] Total Est. Hours: {total_est:.2f}")
                print(f"[DEBUG] Total Completed Hours: {total_completed:.2f}")
            else:
                print(f"[WARN] Missing Est. Hours or To Do in {f}")

            # Flag tasks that are functionally complete but not marked as Completed
            if "To Do" in df.columns and "Status" in df.columns:
                df["ShouldBeCompleted"] = (df["To Do"] == 0) & (df["Status"] != "Completed")

            # Tag Planning Level from filename
            tag = os.path.splitext(os.path.basename(f))[0].replace("tasklist_", "")
            planning_level_map = {
                "CDAS6441": "CDAS - 6441",
                "EDS4834": "EDS-4834",
                "EEB9372": "EEB-9372",
                "UAPIV9443": "UAP-IV-9443",
                "UAPSAL9402": "UAPSAL-9402",
                "UAPSPM9442": "UAP-SPM-9442"
            }
            tag = planning_level_map.get(tag, tag)
            df["Planning Level"] = tag
            print(f"[DEBUG] Tagged as Planning Level: {tag}")

            dfs.append(df)

        except Exception as e:
            print(f"[ERROR] Failed to read {f}: {str(e)}")

    if dfs:
        tasklist_df = pd.concat(dfs, ignore_index=True)
        print(f"\n[DEBUG] ===== FINAL MERGED FILE =====")
        print(f"[DEBUG] Total rows: {tasklist_df.shape[0]}")
        print(f"[DEBUG] Total columns: {tasklist_df.shape[1]}")

        # Debug: Print row counts and hours per planning level
        if 'Planning Level' in tasklist_df.columns:
            print(f"\n[DEBUG] Summary by Planning Level:")
            for pl in sorted(tasklist_df['Planning Level'].unique()):
                pl_df = tasklist_df[tasklist_df['Planning Level'] == pl]
                row_count = len(pl_df)
                completed_hours = pl_df['Completed Hours'].sum() if 'Completed Hours' in pl_df.columns else 0
                est_hours = pl_df['Est. Hours'].sum() if 'Est. Hours' in pl_df.columns else 0
                print(f"  {pl}: {row_count} rows, Est: {est_hours:.2f}h, Completed: {completed_hours:.2f}h")

        # Debug: Check for duplicate IDs
        if 'ID' in tasklist_df.columns:
            duplicate_ids = tasklist_df[tasklist_df.duplicated(subset=['ID'], keep=False)]
            if not duplicate_ids.empty:
                print(f"\n[WARN] Found {len(duplicate_ids)} rows with duplicate IDs")
                print(f"[WARN] Unique duplicate IDs: {duplicate_ids['ID'].nunique()}")
                print(f"[INFO] This is expected if tasks belong to multiple Planning Levels")

        tasklist_df.to_excel(FINAL_OUTPUT, index=False, engine="openpyxl")
        print(f"\n[SUCCESS] Combined Excel saved to {FINAL_OUTPUT}")
    else:
        print("[ERROR] No files to merge")

if __name__ == "__main__":
    run_playwright()
