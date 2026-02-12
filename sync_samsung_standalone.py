import json
import os
from account_manager import Account, create_split_account, save_accounts, load_accounts

def sync_existing_purchase():
    print("--- Standalone Samsung Sync Script ---")
    state_file = "trade_state.json"
    
    # 1. Load config
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    total_capital = config.get("total_capital", 0)
    
    # 2. Load existing state or create map
    loaded_accounts = load_accounts(state_file)
    accounts_map = {}
    
    if loaded_accounts:
        for acc in loaded_accounts:
            accounts_map[acc.account_id] = acc
    else:
        # Replicate initialize_accounts logic without PyQt5/Kiwoom imports
        for strategy in config.get("strategies", []):
            s_id = strategy["id"]
            strategy_capital = total_capital * strategy.get("total_allocation_percent", 0)
            
            sub_accounts = strategy.get("accounts", [])
            strat_configs = []
            for acc_cfg in sub_accounts:
                cfg = acc_cfg.copy()
                cfg["account_id"] = f"{s_id}_{acc_cfg['suffix']}"
                strat_configs.append(cfg)
            
            new_accounts = create_split_account(
                strategy_capital, 
                len(sub_accounts), 
                [acc["ratio"] for acc in sub_accounts], 
                strat_configs,
                stock_code=strategy["stock_code"]
            )
            for acc in new_accounts:
                accounts_map[acc.account_id] = acc

    # 3. Find Samsung Leader
    samsung_leader = accounts_map.get("Samsung_1")
    if not samsung_leader:
        print("Error: Samsung_1 not found.")
        return

    if samsung_leader.holdings:
        print(f"Skipping: Samsung_1 already has holdings: {samsung_leader.holdings}")
    else:
        # Record 4M KRW purchase
        price = 60600
        qty = 66
        samsung_leader.buy(
            code="005930", 
            price=price, 
            qty=qty, 
            timestamp="2026-02-11 15:00:00",
            note="Manual sync for existing purchase"
        )
        print(f"✅ Recorded {qty} shares @ {price} in Samsung_1")

    # 4. Save
    save_accounts(list(accounts_map.values()), state_file)
    print(f"✅ State saved to {state_file}")

if __name__ == "__main__":
    sync_existing_purchase()
