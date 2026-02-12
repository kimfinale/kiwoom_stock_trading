from account_manager import load_accounts, save_accounts
from real_time_trader import initialize_accounts
import os

def sync_existing_purchase():
    print("--- Samsung Sync Script ---")
    state_file = "trade_state.json"
    
    # 1. Load or Initialize
    accounts_map = initialize_accounts("config.json")
    accounts = list(accounts_map.values())

    # 2. Find Samsung Leader
    acc_id = "Samsung_1"
    samsung_leader = accounts_map.get(acc_id)

    if not samsung_leader:
        print(f"Error: Could not find {acc_id}. Ensure config.json is correct.")
        return

    # 3. Check if already has holdings
    if samsung_leader.holdings:
        print(f"Account {acc_id} already has holdings: {samsung_leader.holdings}")
        print("No changes made.")
        return

    # 4. Record the 4,000,000 KRW purchase
    # We'll use 66 shares at 60,600 KRW as a representative split for 4M KRW.
    # You can adjust these numbers to match your actual receipt.
    price = 60600
    qty = 66
    total_cost = price * qty
    
    print(f"Recording purchase of {qty} shares @ {price:,} KRW (Total: {total_cost:,} KRW)...")
    
    # We use buy() which updates balance and holdings automatically
    success, msg = samsung_leader.buy(
        code="005930", 
        price=price, 
        qty=qty, 
        timestamp="2026-02-11 15:00:00", # Yesterday afternoon
        note="Manual sync for existing purchase"
    )

    if success:
        save_accounts(accounts, state_file)
        print("✅ Success: trade_state.json updated.")
        print(f"New Balance for {acc_id}: {samsung_leader.balance:,} KRW")
    else:
        print(f"❌ Failed to record purchase: {msg}")

if __name__ == "__main__":
    sync_existing_purchase()
