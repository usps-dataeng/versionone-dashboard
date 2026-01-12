import os
os.environ["PLAYWRIGHT_SKIP_VALIDATE_DEPENDENCIES"] = "1"
from playwright_advanced import run_playwright
from datetime import datetime

# Set environment variable to skip Playwright dependency validation
os.environ["PLAYWRIGHT_SKIP_VALIDATE_DEPENDENCIES"] = "1"

# Confirm script is being reached
with open("automation_log.txt", "a", encoding="utf-8", errors="replace") as log:
    log.write(f"[DEBUG] Script reached at {datetime.now()}\n")

# Import and run Playwright
from playwright_advanced import run_playwright

with open("automation_log.txt", "a", encoding="utf-8", errors="replace") as log:
    log.write(f"[INFO] Starting Playwright at {datetime.now()}\n")

try:
    run_playwright()
    with open("automation_log.txt", "a", encoding="utf-8", errors="replace") as log:
        log.write(f"[INFO] Playwright completed at {datetime.now()}\n")

    # Push to GitHub after successful scraping
    from auto_push import push_to_github
    with open("automation_log.txt", "a", encoding="utf-8", errors="replace") as log:
        log.write(f"[INFO] Starting git push at {datetime.now()}\n")

    push_to_github()

    with open("automation_log.txt", "a", encoding="utf-8", errors="replace") as log:
        log.write(f"[INFO] Git push completed at {datetime.now()}\n")

except Exception as e:
    with open("automation_log.txt", "a", encoding="utf-8", errors="replace") as log:
        log.write(f"[ERROR] Workflow failed: {str(e)}\n")

