import sys
import time
import json
import subprocess
import os
from PyQt5.QtWidgets import QApplication
from kiwoom_api import Kiwoom
# from state_manager import StateManager # Deprecated
from account_manager import Account, create_split_account, save_accounts, load_accounts
from strategy_executor import StrategyExecutor
from github_sync import GitHubSync
from generate_portfolio_json import fetch_and_generate_portfolio
from datetime import datetime, time as dtime

def check_market_open():
    """
    Check if KOSPI/KOSDAQ market is open (09:00 - 15:30 KST).
    Returns True if open, False otherwise.
    Also returns False on weekends.
    """
    now = datetime.now()
    
    # Weekday check (0=Mon, 6=Sun)
    if now.weekday() >= 5:
        return False
        
    current_time = now.time()
    start_time = dtime(9, 0)
    end_time = dtime(15, 30)
    
    return start_time <= current_time <= end_time

def initialize_accounts(config):
    """
    Initialize accounts from state file or create new ones from config.
    Returns a dictionary of {account_id: Account object}.
    """
    if isinstance(config, str):
        with open(config, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
    state_file = "trade_state.json"
    loaded_accounts = load_accounts(state_file)
    
    accounts_map = {}
    
    if loaded_accounts:
        print(f"Loaded {len(loaded_accounts)} accounts from {state_file}")
        for acc in loaded_accounts:
            accounts_map[acc.account_id] = acc
    
    # Merge with config (handles new stocks/accounts added to config.json)
    total_capital = config.get("total_capital", 0)
    newly_created = 0
    
    if "strategies" in config:
        for strategy in config["strategies"]:
            s_id = strategy["id"]
            alloc_percent = strategy.get("total_allocation_percent", 0)
            strategy_capital = total_capital * alloc_percent
            
            sub_accounts = strategy.get("accounts", [])
            num_subs = len(sub_accounts)
            ratios = [acc["ratio"] for acc in sub_accounts]
            
            # Prepare strategy configs for each sub-account
            strat_configs = []
            for acc_cfg in sub_accounts:
                acc_id = f"{s_id}_{acc_cfg['suffix']}"
                
                # Only create if not already in state
                if acc_id not in accounts_map:
                    cfg = acc_cfg.copy()
                    cfg["account_id"] = acc_id
                    cfg["strategy_id"] = s_id
                    cfg["stock_code"] = strategy["stock_code"]
                    strat_configs.append(cfg)
                else:
                    # Fill slot to keep indexing matched for create_split_account if needed
                    # but create_split_account logic below needs adjustment
                    strat_configs.append(None) 
            
            # If we have missing accounts in this strategy group
            if any(cfg is not None for cfg in strat_configs):
                # We need to selectively create. 
                # For simplicity, we can just instantiate Account objects directly here
                for i, cfg in enumerate(strat_configs):
                    if cfg:
                        acc_id = cfg["account_id"]
                        allocated_capital = int(strategy_capital * ratios[i])
                        
                        new_acc = Account(
                            account_id=acc_id,
                            principal=allocated_capital,
                            stock_code=strategy["stock_code"],
                            strategy_config=cfg
                        )
                        accounts_map[acc_id] = new_acc
                        newly_created += 1
                        print(f"  Merged New Account {acc_id}: Principal {new_acc.principal:,} KRW")

    if newly_created > 0 or not loaded_accounts:
        save_accounts(list(accounts_map.values()), state_file)
        if newly_created > 0:
            print(f"Added {newly_created} new accounts from config to state.")
        
    return accounts_map

def update_account_snapshots(kiwoom, accounts_map):
    """
    Update all accounts with current price snapshots.
    This populates the performance_log for historical data.

    Args:
        kiwoom: Kiwoom API instance
        accounts_map: Dictionary of {account_id: Account}

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Collect all unique stock codes from holdings
        all_codes = set()
        for acc in accounts_map.values():
            all_codes.update(acc.holdings.keys())

        if not all_codes:
            # No holdings, just record snapshots with current balance
            for acc in accounts_map.values():
                acc.update_snapshot({})
            return True

        # Fetch current prices for all stocks
        current_prices = {}
        for code in all_codes:
            time.sleep(0.2) # Prevent Rate Limiting
            try:
                data = kiwoom.get_current_price(code)
                if data and 'price' in data:
                    price = abs(int(data['price']))
                    if price > 0:
                        current_prices[code] = price
                    else:
                        print(f"  Warning: Invalid price for {code}: {price}")
                else:
                    print(f"  Warning: Invalid data for {code}: {data}")
            except Exception as e:
                print(f"  Warning: Failed to get price for {code}: {e}")

        # Update each account's snapshot
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for acc in accounts_map.values():
            try:
                acc.update_snapshot(current_prices, timestamp=timestamp)
            except Exception as e:
                print(f"  Warning: Failed to update snapshot for {acc.account_id}: {e}")

        return True

    except Exception as e:
        print(f"Error updating account snapshots: {e}")
        traceback.print_exc()
        return False

def main():
    """
    Real-time trading bot with independent execution intervals.
    
    Intervals (Configurable):
    - Price Check & Follower Trading: ~1 min
    - Leader Buying: ~20 min (throttled)
    - Dashboard Update: ~10 min
    """
    # Load configuration
    config_path = 'config.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Initialize Qt Application
    app = QApplication(sys.argv)

    # Connect to Kiwoom API
    print("=" * 60)
    print("Real-Time Trading Bot - Starting")
    print("=" * 60)
    kiwoom = Kiwoom()

    print("\nConnecting to Kiwoom API...")
    try:
        kiwoom.comm_connect()
        print("✅ Connected to Kiwoom API")
    except Exception as e:
        print(f"\n❌ Connection Failed: {e}")
        sys.exit(1)

    # Get account information
    accounts_list = kiwoom.get_login_info("ACCNO")
    if not accounts_list:
        print("ERROR: No accounts found. Exiting.")
        sys.exit(1)

    # Select the account to use
    real_account_no = config.get("real_account_id", accounts_list[0])
    print(f"Using Real Account: {real_account_no}")

    # Initialize Virtual Accounts
    print("\n" + "=" * 60)
    print("Initializing Accounts")
    print("=" * 60)
    accounts_map = initialize_accounts(config)

    # Initialize GitHub Sync
    github_sync = GitHubSync()

    # Transaction Callback
    def on_transaction_complete(action, account_alias, code, price, qty):
        print(f"\n{'─'*60}")
        print(f"✅ Transaction: {action} {qty} {code} @ {price:,} KRW ({account_alias})")
        print(f"{'─'*60}\n")
        try:
            save_accounts(list(accounts_map.values()), "trade_state.json")
        except Exception as e:
            print(f"Warning: Failed to save state: {e}")

    # Initialize StrategyExecutor
    executor = StrategyExecutor(
        kiwoom,
        accounts_map,
        config,
        on_transaction_complete=on_transaction_complete
    )

    # Display configuration
    print("\n" + "=" * 60)
    print("Configuration")
    print("=" * 60)
    print(f"Total Capital  : {config.get('total_capital', 0):,} KRW")
    
    intervals = config.get("execution_intervals", {})
    check_interval_min = intervals.get("check_interval_minutes", 1)
    dashboard_interval_min = intervals.get("dashboard_interval_minutes", 10)

    print(f"Intervals:")
    print(f"  - Price/Follower Check : {check_interval_min} min")
    print(f"  - Leader Buy Frequency : once per day (per strategy)")
    print(f"  - Dashboard Update     : {dashboard_interval_min} min")
    print("-" * 60)

    # Confirm before starting
    if not config.get('dry_run', False):
        print("\n" + "!" * 60)
        print("WARNING: DRY RUN MODE IS OFF - REAL TRADES WILL BE EXECUTED")
        print("!" * 60)
        response = input("\nType 'START' to begin real trading: ")
        if response.strip().upper() != 'START':
            print("Aborted by user.")
            sys.exit(0)

    # Main execution loop
    print("\n" + "=" * 60)
    print("Starting Trading Loop")
    print("=" * 60)
    print("Press Ctrl+C to stop safely\n")

    # Timestamps for interval tracking
    now = time.time()
    last_price_check_time = 0 # Force immediate run
    last_dashboard_time = 0 # Force immediate run
    
    # File monitoring
    try:
        last_mtime = os.path.getmtime(config_path)
    except OSError:
        last_mtime = 0

    iteration = 0

    try:
        while True:
            # Responsive Sleep (1 sec tick)
            time.sleep(1)
            now = time.time()
            
            # --- Config Reload Monitor ---
            try:
                current_mtime = os.path.getmtime(config_path)
                if current_mtime > last_mtime:
                    print(f"\n🔄 Configuration file changed! Reloading...")
                    time.sleep(0.5) # Wait for write
                    with open(config_path, 'r', encoding='utf-8') as f:
                        new_config = json.load(f)
                    
                    config = new_config
                    last_mtime = current_mtime
                    executor.update_config(config)
                    
                    # Update Intervals
                    intervals = config.get("execution_intervals", {})
                    check_interval_min = intervals.get("check_interval_minutes", 1)
                    dashboard_interval_min = intervals.get("dashboard_interval_minutes", 10)
                    print(f"   Intervals Updated: Check={check_interval_min}m, Dash={dashboard_interval_min}m")
            except OSError:
                pass

            # --- Check Market Hours ---
            if not check_market_open() and not config.get("ignore_market_hours", False):
                 dt_now = datetime.now()
                 if dt_now.weekday() >= 5 or dt_now.time() >= dtime(15, 31):
                     print(f"\n[{dt_now.strftime('%H:%M:%S')}] Market closed for the day. Exiting ...")
                     break

                 if iteration % 60 == 0: # Log every minute
                     print(f"[{dt_now.strftime('%H:%M:%S')}] Market closed. Waiting...", end='\r')
                 continue

            # ==============================================================================
            # Core Logic - Independent Intervals
            # ==============================================================================
            
            # 1. Price Check & Trading (Base Frequency: check_interval_min)
            if now - last_price_check_time >= check_interval_min * 60:
                iteration += 1
                last_price_check_time = now
                current_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"\nTime: {current_str} | Tick #{iteration}")
                
                # A. Execute Strategy (Price Check + Buy/Sell)
                # Leader buy frequency is managed per-strategy inside StrategyExecutor (once per day)
                executor.execute_step(allow_leader_buy=True)
                
                # B. Update Snapshots (for Graph)
                update_account_snapshots(kiwoom, accounts_map)
                
                # C. Save State
                save_accounts(list(accounts_map.values()), "trade_state.json")
            
            # 2. Dashboard Update & GitHub Sync (Independent Frequency)
            if now - last_dashboard_time >= dashboard_interval_min * 60:
                last_dashboard_time = now
                print(f"\n🔄 Syncing Dashboard (Every {dashboard_interval_min} min)...")
                
                try:
                    fetch_and_generate_portfolio(kiwoom)
                    commit_msg = f"Auto-update: {datetime.now().strftime('%H:%M:%S')}"
                    github_sync.sync_portfolio(commit_message=commit_msg)
                    print("✅ Dashboard synced.")
                except Exception as e:
                    print(f"⚠️ Dashboard sync failed: {e}")

    except KeyboardInterrupt:
        print("\n\n" + "=" * 60)
        print("Trading Bot Stopped by User")
        print("=" * 60)
        # Save Final State
        save_accounts(list(accounts_map.values()), "trade_state.json")
        print("✅ Final state saved.")

if __name__ == "__main__":
    main()
