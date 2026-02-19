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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "outputs")
PORTFOLIO_FILE = os.path.join(OUTPUT_DIR, "portfolio.json")
MAX_HISTORY_DAYS = 60

def load_portfolio(filepath=PORTFOLIO_FILE):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading existing portfolio: {e}")
    return DEFAULT_PORTFOLIO

def fetch_and_generate_portfolio(kiwoom):
    """
    Fetches data using an existing Kiwoom instance and generates portfolio.json.
    """
    # Ensure output directory exists
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created directory: {OUTPUT_DIR}")

    print("Fetching account info...")
    accounts_list = kiwoom.get_login_info("ACCNO")
    if not accounts_list:
        print("No accounts found.")
        return False

    # Load Config for Sector Map & Virtual Accounts
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    print(f"Loading config from: {config_path}")
    sector_map = {}
    config = {}

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # Build Sector Map
            if "strategies" in config:
                for strategy in config["strategies"]:
                    if "stock_code" in strategy and "sector" in strategy:
                        sector_map[strategy["stock_code"]] = strategy["sector"]
        except Exception as e:
            print(f"Error loading config: {e}")

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
        if acc == '7032756831': continue # Skip unused account
        print(f"Processing Account: {acc}")

        # 1. Get Cash (Deposit)
        # opw00001
        kiwoom.get_deposit(acc)
        cash = kiwoom.tr_data
        if cash is None: cash = 0

        # 2. Get Evaluation & Holdings
        # opw00018
        data = kiwoom.get_account_evaluation(acc)
        if not data or not isinstance(data, dict):
            print(f"Failed to get evaluation for {acc} (Data: {data})")
            # Add partial data if possible or skip
            accounts_data.append({
                "name": f"Account {acc}",
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
        equity = summary['total_eval']
        acc_total_value = summary['estimated_assets']

        acc_equity = equity
        acc_total_val = summary['estimated_assets']
        acc_cash = acc_total_val - acc_equity  # Derive cash to ensure consistency

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
            code = h['code']
            sector = sector_map.get(code, "Unknown")

            holding_entry = {
                "name": h['name'],
                "symbol": code,
                "sector": sector,
                "quantity": h['qty'],
                "avg_price": h['buy_price'],
                "current_price": h['current_price'],
                "value": h['current_price'] * h['qty'],
                "pnl": h['eval_profit'],
                "pnl_percent": h['yield_rate'],
                "account": f"Account {acc}"
            }
            holdings_list.append(holding_entry)

        time.sleep(0.3)

    # Load and Update History (before summary so we can compute daily P&L)
    portfolio = load_portfolio()
    history = portfolio.get("history", [])
    history.sort(key=lambda x: x['date'])

    today_str = datetime.date.today().strftime("%Y-%m-%d")

    # Find previous day's value for daily P&L calculation
    prev_value = None
    for entry in reversed(history):
        if entry["date"] < today_str:
            prev_value = entry["value"]
            break

    # Update or append today's entry
    todays_entry = next((item for item in history if item["date"] == today_str), None)
    if todays_entry:
        todays_entry["value"] = total_value
    else:
        history.append({
            "date": today_str,
            "value": total_value
        })

    # Sort and limit history
    history.sort(key=lambda x: x['date'])
    if len(history) > MAX_HISTORY_DAYS:
        history = history[-MAX_HISTORY_DAYS:]

    # Calculate Global Summaries
    total_capital = config.get("total_capital", 100000000)
    total_pnl_all = total_value - total_capital

    # Daily P&L from history (today vs previous day)
    daily_pnl_all = 0
    daily_return = 0.0
    if prev_value is not None and prev_value > 0:
        daily_pnl_all = total_value - prev_value
        daily_return = round((daily_pnl_all / prev_value) * 100, 2)

    if total_value > 0:
        cash_percent = round((total_cash_all / total_value) * 100, 2)
        total_rate = round((total_pnl_all / total_capital) * 100, 2)
    else:
        cash_percent = 0.0
        total_rate = 0.0

    summary_obj = {
        "total_value": total_value,
        "daily_pnl": daily_pnl_all,
        "daily_return": daily_return,
        "total_pnl": total_pnl_all,
        "total_return": total_rate,
        "cash": total_cash_all,
        "cash_percent": cash_percent
    }

    # --- Virtual Accounts Logic ---
    virtual_accounts_data = []

    # Load trade_state.json for actual per-virtual-account holdings
    trade_state_path = os.path.join(script_dir, "trade_state.json")
    trade_state = []
    if os.path.exists(trade_state_path):
        try:
            with open(trade_state_path, "r", encoding="utf-8") as f:
                trade_state = json.load(f)
            print(f"Loaded trade_state.json with {len(trade_state)} virtual accounts")
        except Exception as e:
            print(f"Error loading trade_state.json: {e}")

    if trade_state:
        try:
            # Build current price map from Kiwoom holdings data
            current_price_map = {}
            for h in holdings_list:
                current_price_map[h['symbol']] = h['current_price']

            # Build sector map from config strategies
            strategy_sector_map = {}
            if config and "strategies" in config:
                for strategy in config["strategies"]:
                    strategy_sector_map[strategy["id"]] = strategy.get("sector", "Unknown")

            target_acc_name = f"Account {config.get('real_account_id', '8119599511')}"

            for va in trade_state:
                v_name = va.get("account_id", "")
                v_balance = va.get("balance", 0)
                v_holdings = va.get("holdings", {})
                v_principal = va.get("principal", 0)
                stock_code = va.get("stock_code", "")

                # Calculate equity using current market prices
                v_equity = 0
                v_cost = 0
                for code, holding in v_holdings.items():
                    qty = holding.get("qty", 0)
                    cur_price = current_price_map.get(code, holding.get("avg_price", 0))
                    v_equity += qty * cur_price
                    v_cost += holding.get("total_cost", 0)

                v_cash = int(v_balance)
                v_total = v_cash + v_equity
                v_pnl = v_equity - v_cost  # PnL = market value - cost basis

                # Extract strategy ID from account_id (e.g., "Samsung_1" -> "Samsung")
                strategy_id = "_".join(v_name.split("_")[:-1]) if "_" in v_name else v_name
                sector = strategy_sector_map.get(strategy_id, "Unknown")

                # Get allocation ratio from strategy config
                s_config = va.get("strategy_config", {})
                ratio = s_config.get("ratio", 0)
                # Find strategy allocation percent
                s_alloc = 0.1  # default
                if config and "strategies" in config:
                    for strategy in config["strategies"]:
                        if strategy["id"] == strategy_id:
                            s_alloc = strategy.get("total_allocation_percent", 0.1)
                            break

                # Extract strategy params
                strategy_type = s_config.get("strategy_type", "")
                params = s_config.get("params", {})
                target_profit = params.get("target_profit", 0)
                dip = params.get("dip", 0)

                # Count buy and sell transactions, and sum realized P&L
                history = va.get("history", [])
                buy_count = sum(1 for t in history if t.get("action") == "BUY")
                sell_count = sum(1 for t in history if t.get("action") == "SELL")
                realized_pnl = int(sum(t.get("pnl", 0) for t in history if t.get("action") == "SELL"))

                virtual_accounts_data.append({
                    "name": v_name,
                    "real_account_ref": target_acc_name,
                    "allocation_ratio": ratio * s_alloc,
                    "strategy_type": strategy_type,
                    "rise_pct": round(target_profit * 100, 1),
                    "dip_pct": round(dip * 100, 1),
                    "total_value": v_total,
                    "cash": v_cash,
                    "equity": v_equity,
                    "unrealized_pnl": v_pnl,
                    "realized_pnl": realized_pnl,
                    "buy_count": buy_count,
                    "sell_count": sell_count,
                    "sector": sector
                })

        except Exception as e:
            print(f"Error processing virtual accounts from trade_state: {e}")
    elif config:
        # Fallback: old ratio-based splitting if no trade_state.json
        try:
            target_acc_data = None
            target_id = config.get("real_account_id", "8119599511")
            for ad in accounts_data:
                if target_id in ad['name']:
                    target_acc_data = ad
                    break
            if not target_acc_data and accounts_data:
                target_acc_data = accounts_data[0]

            if target_acc_data and "strategies" in config:
                stock_value_map = {}
                stock_cost_map = {}
                stock_pnl_map = {}
                for h in holdings_list:
                    code = h.get('symbol', '')
                    stock_value_map[code] = h['value']
                    stock_cost_map[code] = h['avg_price'] * h['quantity']
                    stock_pnl_map[code] = h['pnl']

                total_capital = config.get("total_capital", target_acc_data.get('total_value', 0))

                for strategy in config["strategies"]:
                    s_id = strategy["id"]
                    s_alloc = strategy["total_allocation_percent"]
                    stock_code = strategy.get("stock_code", "")
                    strategy_capital = total_capital * s_alloc
                    actual_stock_value = stock_value_map.get(stock_code, 0)
                    actual_stock_cost = stock_cost_map.get(stock_code, 0)
                    actual_stock_pnl = stock_pnl_map.get(stock_code, 0)
                    strategy_cash = strategy_capital - actual_stock_cost

                    for acc in strategy["accounts"]:
                        ratio = acc["ratio"]
                        suffix = acc["suffix"]
                        v_name = f"{s_id}_{suffix}"
                        v_equity = int(actual_stock_value * ratio)
                        v_cash = int(strategy_cash * ratio)
                        v_pnl = int(actual_stock_pnl * ratio)
                        v_val = v_cash + v_equity

                        virtual_accounts_data.append({
                            "name": v_name,
                            "real_account_ref": target_acc_data['name'],
                            "allocation_ratio": ratio * s_alloc,
                            "total_value": v_val,
                            "cash": v_cash,
                            "equity": v_equity,
                            "total_pnl": v_pnl,
                            "sector": strategy.get("sector", "Unknown")
                        })

        except Exception as e:
            print(f"Error processing virtual accounts: {e}")

    # Add realized/unrealized P&L totals to summary
    # Realized P&L: sum from virtual account sell history
    total_realized = sum(va.get("realized_pnl", 0) for va in virtual_accounts_data)
    # Unrealized P&L: derive from total return - realized to ensure consistency
    # (total_return = unrealized + realized)
    total_unrealized = total_pnl_all - total_realized
    summary_obj["realized_pnl"] = total_realized
    summary_obj["unrealized_pnl"] = total_unrealized

    # Final Structure
    final_json = {
        "summary": summary_obj,
        "history": history,
        "holdings": holdings_list,
        "accounts": accounts_data,
        "virtual_accounts": virtual_accounts_data
    }

    # Save
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    print(f"Successfully generated {PORTFOLIO_FILE}")
    print(json.dumps(final_json, indent=2, ensure_ascii=False))
    return True

def main():
    app = QApplication(sys.argv)
    kiwoom = Kiwoom()
    print("Connecting to Kiwoom API...")
    kiwoom.comm_connect()
    time.sleep(1)

    fetch_and_generate_portfolio(kiwoom)

if __name__ == "__main__":
    main()
