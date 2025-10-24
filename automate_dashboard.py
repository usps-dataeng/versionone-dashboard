from datetime import datetime

with open("automation_log.txt", "a") as log:
    log.write(f"{datetime.now()} - Task ran\n")

# automate_dashboard.py
from playwright_advanced import run_playwright
from auto_push import push_to_github

run_playwright()
push_to_github()
