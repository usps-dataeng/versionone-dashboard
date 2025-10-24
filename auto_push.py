import subprocess
import os
def push_to_github():
    repo_path = "C:/Users/tbh2j0/OneDrive - USPS/Test Folder/versionone_dashboard"
    os.chdir(repo_path)

    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "Auto-update task_quicklist.xlsx"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("✅ Git push complete.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Git push failed: {e}")

if __name__ == "__main__":
    push_to_github()

