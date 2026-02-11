import os
import shutil
import subprocess
import glob
import sys

OUTPUT_DIR = "outputs"

def run_command(command):
    print(f"Running: {command}")
    try:
        subprocess.check_call(command, shell=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        return False

def main():
    # 1. Ensure output directory exists (also handled in generate_portfolio_json.py but good to be safe)
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created directory: {OUTPUT_DIR}")

    # 2. Move CSV files
    csv_files = glob.glob("*.csv")
    print(f"Found {len(csv_files)} CSV files in root.")
    
    for file in csv_files:
        dest_path = os.path.join(OUTPUT_DIR, file)
        try:
            shutil.move(file, dest_path)
            print(f"Moved {file} -> {dest_path}")
        except Exception as e:
            print(f"Failed to move {file}: {e}")

    # 3. Git Operations
    print("\nStarting Git Sync...")
    
    # Check if this is a git repo
    if not os.path.exists(".git"):
        print("Not a git repository. Skipping git operations.")
        return

    # Git Add
    if not run_command(f"git add {OUTPUT_DIR}"):
        print("Git add failed.")
        return

    # Git Commit
    # simple commit message
    if not run_command('git commit -m "Update portfolio outputs and organize CSVs"'):
        print("Git commit failed (nothing to commit?).")
        # Don't return here, might just be nothing to commit but we can still push if ahead
    
    # Git Push
    if not run_command("git push"):
        print("Git push failed.")
        return

    print("\nSync completed successfully.")

if __name__ == "__main__":
    main()
