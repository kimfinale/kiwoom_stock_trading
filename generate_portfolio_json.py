import sys
import json
import time
import datetime
import os
from PyQt5.QtWidgets import QApplication
from kiwoom_api import Kiwoom

# Default Portfolio Structure
DEFAULT_PORTFOLIO = {
    "summary": {
        "total_value": 0,
        "daily_pnl": 0,
        "daily_return": 0.0,
        "total_pnl": 0,
        "total_return": 0.0,
        "cash": 0,
        "cash_percent": 0.0
    },
    "history": [],
    "holdings": [],
    "accounts": []
}

OUTPUT_DIR = "outputs"
PORTFOLIO_FILE = os.path.join(OUTPUT_DIR, "portfolio.json")

def load_portfolio(filepath=PORTFOLIO_FILE):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading existing portfolio: {e}")
    return DEFAULT_PORTFOLIO

def main():
    # Ensure output directory exists
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created directory: {OUTPUT_DIR}")

    app = QApplication(sys.argv)
    kiwoom = Kiwoom()
    print("Connecting to Kiwoom API...")
    kiwoom.comm_connect()
    
    # Wait a bit for connection to stabilize
    time.sleep(1)

    print("Fetching account info...")
    accounts_list = kiwoom.get_login_info("ACCNO")
    if not accounts_list:
        print("No accounts found.")
        sys.exit(0)
    
    # Data Aggregators
    total_value = 0
    total_cash_all = 0
    total_equity_all = 0
    total_pnl_all = 0 # Total Inception PnL
    daily_pnl_all = 0
    
    holdings_list = []
    accounts_data = []
    
    # Iterate accounts
    for acc in accounts_list:
        if not acc: continue
        print(f"Processing Account: {acc}")
        
        # 1. Get Cash (Deposit)
        # opw00001
        kiwoom.get_deposit(acc)
        cash = kiwoom.tr_data
        if cash is None: cash = 0
        
        # 2. Get Evaluation & Holdings
        # opw00018
        data = kiwoom.get_account_evaluation(acc)
        if not data:
            print(f"Failed to get evaluation for {acc}")
            # Add partial data if possible or skip
            accounts_data.append({
                "name": f"Account {acc}", # Masking or using ID? Using ID for now as requested format example shows "Account #1"
                "total_value": cash,
                "cash": cash,
                "equity": 0
            })
            total_value += cash
            total_cash_all += cash
            continue
            
        summary = data['summary']
        acc_holdings = data['holdings']
        
        # Extract Summary Data
        # summary keys: total_buy, total_eval, total_profit_loss, total_rate, estimated_assets, daily_pnl
        equity = summary['total_eval']
        acc_total_value = summary['estimated_assets']
        
        # Kiwoom's estimated_assets usually includes cash + equity. 
        # But sometimes there are discrepancies. Let's trust opw00018's estimated_assets for total account value.
        # However, opw00018 might not return "pure cash". 
        # opw00001 returns "orderable amount" which is roughly cash.
        # Let's use opw00001 for cash, and opw00018 evaluation for equity.
        # Total Value = Cash + Equity.
        # Kiwoom 'estimated_assets' = Total Value usually.
        
        # Let's align with requested format:
        # Accounts Array: total_value, cash, equity
        
        acc_equity = equity
        acc_cash = cash # From opw00001
        
        # If opw00018 estimated_assets is reliable, use it as Total Value.
        # Otherwise Cash + Equity. 
        # Sometimes estimated_assets includes untradeable cash etc.
        # Let's use Cash + Equity for consistency if they differ significantly? 
        # Actually Kiwoom's estimated_assets is usually the "Real Asset Value".
        acc_total_val = summary['estimated_assets'] 
        
        # Update Global Totals
        total_value += acc_total_val
        total_cash_all += acc_cash
        total_equity_all += acc_equity
        total_pnl_all += summary['total_profit_loss']
        daily_pnl_all += summary.get('daily_pnl', 0)
        
        accounts_data.append({
            "name": f"Account {acc}",
            "total_value": acc_total_val,
            "cash": acc_cash,
            "equity": acc_equity
        })
        
        # Process Holdings
        for h in acc_holdings:
            # h keys: name, code, qty, buy_price, current_price, eval_profit, yield_rate
            
            # Format: name, symbol, sector, quantity, avg_price, current_price, value, pnl, pnl_percent, account
            # Sector: default to "Unknown"
            
            holding_entry = {
                "name": h['name'],
                "symbol": h['code'],
                "sector": "Unknown", # Optimization: Skip sector lookup for speed
                "quantity": h['qty'],
                "avg_price": h['buy_price'],
                "current_price": h['current_price'],
                "value": h['current_price'] * h['qty'], # or use h['eval_profit'] + cost? usually price*qty
                "pnl": h['eval_profit'],
                "pnl_percent": h['yield_rate'],
                "account": f"Account {acc}"
            }
            holdings_list.append(holding_entry)
            
        time.sleep(0.3) # Avoid rate limit (though purely calling TR sequentially is usually fine)

    # Calculate Global Summaries
    if total_value > 0:
        cash_percent = round((total_cash_all / total_value) * 100, 2)
        total_rate = round((total_pnl_all / (total_value - total_pnl_all)) * 100, 2) # Approximation of total return if not tracked separately
        # Actually Total PnL / Invested Capital * 100. Invested = Total Value - Total PnL.
        
        # Daily Return: Daily PnL / (Start Value) * 100. Start Value = End Value - Daily PnL.
        start_value_day = total_value - daily_pnl_all
        daily_return = 0.0
        if start_value_day > 0:
            daily_return = round((daily_pnl_all / start_value_day) * 100, 2)
    else:
        cash_percent = 0.0
        total_rate = 0.0
        daily_return = 0.0

    summary_obj = {
        "total_value": total_value,
        "daily_pnl": daily_pnl_all,
        "daily_return": daily_return,
        "total_pnl": total_pnl_all,
        "total_return": total_rate,
        "cash": total_cash_all,
        "cash_percent": cash_percent
    }
    
    # Load and Update History
    portfolio = load_portfolio()
    history = portfolio.get("history", [])
    
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    # Check if today exists, update it if so, else append
    todays_entry = next((item for item in history if item["date"] == today_str), None)
    
    if todays_entry:
        todays_entry["value"] = total_value
    else:
        history.append({
            "date": today_str,
            "value": total_value
        })
        
    # Sort history by date
    history.sort(key=lambda x: x['date'])
    
    # Final Structure
    final_json = {
        "summary": summary_obj,
        "history": history,
        "holdings": holdings_list,
        "accounts": accounts_data
    }
    
    # Save
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully generated {PORTFOLIO_FILE}")
    print(json.dumps(summary_obj, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
