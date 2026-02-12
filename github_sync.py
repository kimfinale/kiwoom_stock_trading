import subprocess
import os
import sys
from datetime import datetime

class GitHubSync:
    """
    Utility class to sync portfolio.json to GitHub repository.
    Assumes the repository is already initialized and has a remote configured.
    """
    
    def __init__(self, repo_path=None, dashboard_repo_path=None):
        """
        Initialize GitHub sync utility.
        
        Args:
            repo_path: Path to the kiwoom_stock_trading repository (current directory)
            dashboard_repo_path: Path to the dashboard repository (if different)
        """
        self.repo_path = repo_path or os.getcwd()
        self.dashboard_repo_path = dashboard_repo_path
        
    def sync_portfolio(self, portfolio_file="outputs/portfolio.json", commit_message=None):
        """
        Sync portfolio.json to GitHub.
        
        Args:
            portfolio_file: Relative path to portfolio.json
            commit_message: Custom commit message (optional)
            
        Returns:
            bool: True if sync successful, False otherwise
        """
        try:
            # Check if file exists
            full_path = os.path.join(self.repo_path, portfolio_file)
            if not os.path.exists(full_path):
                print(f"WARNING: Portfolio file not found: {full_path}")
                return False
            
            # Generate commit message
            if not commit_message:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                commit_message = f"Auto-update portfolio.json - {timestamp}"
            
            # Git operations
            os.chdir(self.repo_path)
            
            # Add the file
            result = subprocess.run(
                ["git", "add", portfolio_file],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"WARNING: Git add failed: {result.stderr}")
                return False
            
            # Check if there are changes to commit
            status_result = subprocess.run(
                ["git", "status", "--porcelain", portfolio_file],
                capture_output=True,
                text=True
            )
            
            if not status_result.stdout.strip():
                print("INFO: No changes to commit in portfolio.json")
                return True
            
            # Commit
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_message],
                capture_output=True,
                text=True
            )
            
            if commit_result.returncode != 0:
                print(f"WARNING: Git commit failed: {commit_result.stderr}")
                return False
            
            # Push
            push_result = subprocess.run(
                ["git", "push"],
                capture_output=True,
                text=True
            )
            
            if push_result.returncode != 0:
                print(f"WARNING: Git push failed: {push_result.stderr}")
                return False
            
            print(f"[OK] Successfully synced {portfolio_file} to GitHub")
            return True
            
        except Exception as e:
            print(f"WARNING: Error during GitHub sync: {e}")
            return False
    
    def sync_to_dashboard_repo(self, portfolio_file="outputs/portfolio.json"):
        """
        Copy portfolio.json to dashboard repository and sync.
        Useful if dashboard is in a separate repository.
        
        Args:
            portfolio_file: Relative path to portfolio.json in current repo
            
        Returns:
            bool: True if sync successful, False otherwise
        """
        if not self.dashboard_repo_path:
            print("WARNING: Dashboard repository path not configured")
            return False
        
        try:
            import shutil
            
            # Source file
            source = os.path.join(self.repo_path, portfolio_file)
            if not os.path.exists(source):
                print(f"WARNING: Source file not found: {source}")
                return False
            
            # Destination (assuming dashboard has src/data/ directory)
            dest_dir = os.path.join(self.dashboard_repo_path, "src", "data")
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            
            dest = os.path.join(dest_dir, "portfolio.json")
            
            # Copy file
            shutil.copy2(source, dest)
            print(f"[OK] Copied {source} to {dest}")
            
            # Git operations in dashboard repo
            os.chdir(self.dashboard_repo_path)
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            commit_message = f"Auto-update portfolio data - {timestamp}"
            
            # Add, commit, push
            subprocess.run(["git", "add", "src/data/portfolio.json"], check=True)
            
            # Check if there are changes
            status_result = subprocess.run(
                ["git", "status", "--porcelain", "src/data/portfolio.json"],
                capture_output=True,
                text=True
            )
            
            if not status_result.stdout.strip():
                print("INFO: No changes to commit in dashboard repository")
                return True
            
            subprocess.run(["git", "commit", "-m", commit_message], check=True)
            subprocess.run(["git", "push"], check=True)
            
            print(f"[OK] Successfully synced to dashboard repository")
            return True
            
        except Exception as e:
            print(f"WARNING: Error syncing to dashboard repo: {e}")
            return False
        finally:
            # Return to original directory
            os.chdir(self.repo_path)


if __name__ == "__main__":
    # Test the sync functionality
    sync = GitHubSync()
    
    print("Testing GitHub sync...")
    success = sync.sync_portfolio()
    
    if success:
        print("[OK] GitHub sync test successful")
    else:
        print("[FAIL] GitHub sync test failed")
