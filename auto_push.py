import subprocess
import os
from datetime import datetime

def push_to_github():
    repo_path = "C:/Users/tbh2j0/OneDrive - USPS/Test Folder/versionone_dashboard"
    os.chdir(repo_path)

    log_file = os.path.join(repo_path, "automation_log.txt")

    try:
        with open(log_file, "a", encoding="utf-8") as log:
            log.write(f"[INFO] Git add at {datetime.now()}\n")
        subprocess.run(["git", "add", "."], check=True, capture_output=True, text=True)

        with open(log_file, "a", encoding="utf-8") as log:
            log.write(f"[INFO] Git commit at {datetime.now()}\n")
        result = subprocess.run(["git", "commit", "-m", "Auto-update task_quicklist.xlsx"],
                              capture_output=True, text=True)

        if result.returncode != 0:
            if "nothing to commit" in result.stdout:
                with open(log_file, "a", encoding="utf-8") as log:
                    log.write(f"[INFO] No changes to commit at {datetime.now()}\n")
                return
            else:
                raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)

        with open(log_file, "a", encoding="utf-8") as log:
            log.write(f"[INFO] Git push at {datetime.now()}\n")
        subprocess.run(["git", "push", "origin", "main"], check=True, capture_output=True, text=True)

        with open(log_file, "a", encoding="utf-8") as log:
            log.write(f"[SUCCESS] Git push complete at {datetime.now()}\n")

    except subprocess.CalledProcessError as e:
        with open(log_file, "a", encoding="utf-8") as log:
            log.write(f"[ERROR] Git failed at {datetime.now()}: {e}\n")
            log.write(f"[ERROR] stdout: {e.stdout}\n")
            log.write(f"[ERROR] stderr: {e.stderr}\n")

if __name__ == "__main__":
    push_to_github()
