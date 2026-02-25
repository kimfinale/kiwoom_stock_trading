"""
Manual Trade Utility — syncs a manual HTS/MTS trade into trade_state.json.

Usage:
  python manual_trade.py --account Samsung_1 --action SELL --code 005930 --price 55000 --qty 3
  python manual_trade.py --account Samsung_1 --action SELL --qty 10 --market   # Auto-fetch current price & stock code
  python manual_trade.py --list                  # Show all accounts and their holdings
  python manual_trade.py --account Samsung_1     # Show details of one account
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime

from account_manager import Account, load_accounts, save_accounts

STATE_FILE = "trade_state.json"


def fetch_market_price(code):
    """Connect to Kiwoom API and fetch the current market price for a stock code."""
    from PyQt5.QtWidgets import QApplication
    from kiwoom_api import Kiwoom

    app = QApplication.instance() or QApplication(sys.argv)
    kiwoom = Kiwoom()

    print("Connecting to Kiwoom API...")
    try:
        kiwoom.comm_connect()
    except Exception as e:
        print(f"Error: Failed to connect to Kiwoom API: {e}")
        sys.exit(1)

    data = kiwoom.get_current_price(code)
    if not data or "price" not in data:
        print(f"Error: Failed to fetch price for {code}")
        sys.exit(1)

    price = abs(data["price"])
    name = data.get("name", code)
    if price == 0:
        print(f"Error: Received invalid price 0 for {code}")
        sys.exit(1)

    print(f"Fetched: {name} ({code}) = {price:,} KRW")
    return price


def load_state():
    accounts = load_accounts(STATE_FILE)
    if not accounts:
        print(f"Error: {STATE_FILE} not found or empty.")
        sys.exit(1)
    return {acc.account_id: acc for acc in accounts}


def print_account_summary(acc):
    print(f"  Account ID : {acc.account_id}")
    print(f"  Principal  : {acc.principal:>12,} KRW")
    print(f"  Balance    : {acc.balance:>12,} KRW")
    strategy_type = acc.strategy_config.get("strategy_type", "?")
    print(f"  Type       : {strategy_type}")
    if acc.holdings:
        for code, h in acc.holdings.items():
            print(f"  Holding    : {code}  qty={h['qty']}  avg={h['avg_price']:,.0f}  cost={h['total_cost']:,.0f}")
    else:
        print(f"  Holding    : (none)")


def list_accounts(accounts_map, filter_id=None):
    for acc_id, acc in sorted(accounts_map.items()):
        if filter_id and acc_id != filter_id:
            continue
        print_account_summary(acc)
        print()


def execute_manual_trade(accounts_map, account_id, action, code, price, qty):
    if account_id not in accounts_map:
        print(f"Error: Account '{account_id}' not found.")
        print(f"Available: {', '.join(sorted(accounts_map.keys()))}")
        sys.exit(1)

    acc = accounts_map[account_id]
    is_leader = acc.strategy_config.get("strategy_type") == "LEADER"

    # Show before state
    print("=" * 50)
    print("BEFORE")
    print("=" * 50)
    print_account_summary(acc)
    print()

    # Preview the trade
    total_value = price * qty
    print("=" * 50)
    print(f"TRADE: {action} {qty} x {code} @ {price:,} = {total_value:,} KRW")
    if is_leader and action == "SELL":
        print("  (Leader no-replenish rule: balance will NOT increase)")
    print("=" * 50)

    # Confirm
    confirm = input("\nProceed? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        sys.exit(0)

    # Backup state file
    backup_path = STATE_FILE + ".bak"
    shutil.copy2(STATE_FILE, backup_path)
    print(f"Backup saved to {backup_path}")

    # Execute
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if action == "BUY":
        success, msg = acc.buy(code, price, qty, timestamp=timestamp, note="manual trade")
        if not success:
            print(f"Error: {msg}")
            sys.exit(1)

    elif action == "SELL":
        pre_sell_balance = acc.balance
        success, msg = acc.sell(code, price, qty, timestamp=timestamp, note="manual trade")
        if not success:
            print(f"Error: {msg}")
            sys.exit(1)
        # No-replenish rule for leader accounts
        if is_leader:
            acc.balance = pre_sell_balance

    # Show after state
    print()
    print("=" * 50)
    print("AFTER")
    print("=" * 50)
    print_account_summary(acc)
    print()

    # Save
    save_accounts(list(accounts_map.values()), STATE_FILE)
    print(f"State saved to {STATE_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Manual trade utility for trade_state.json")
    parser.add_argument("--list", action="store_true", help="List all accounts")
    parser.add_argument("--account", type=str, help="Account ID (e.g. Samsung_1)")
    parser.add_argument("--action", type=str, choices=["BUY", "SELL"], help="Trade action")
    parser.add_argument("--code", type=str, help="Stock code (e.g. 005930)")
    parser.add_argument("--price", type=int, help="Trade price")
    parser.add_argument("--qty", type=int, help="Quantity")
    parser.add_argument("--market", action="store_true", help="Fetch current market price via Kiwoom API (--price and --code become optional)")
    args = parser.parse_args()

    accounts_map = load_state()

    if args.list or (args.account and not args.action):
        list_accounts(accounts_map, filter_id=args.account)
        return

    # --market mode: resolve code and price automatically
    if args.market and args.account and args.action and args.qty:
        acc = accounts_map.get(args.account)
        if not acc:
            print(f"Error: Account '{args.account}' not found.")
            print(f"Available: {', '.join(sorted(accounts_map.keys()))}")
            sys.exit(1)

        code = args.code or acc.stock_code
        if not code:
            print("Error: Could not determine stock code. Provide --code explicitly.")
            sys.exit(1)

        price = args.price or fetch_market_price(code)
        execute_manual_trade(accounts_map, args.account, args.action, code, price, args.qty)
        return

    if not all([args.account, args.action, args.code, args.price, args.qty]):
        parser.print_help()
        sys.exit(1)

    execute_manual_trade(accounts_map, args.account, args.action, args.code, args.price, args.qty)


if __name__ == "__main__":
    main()
