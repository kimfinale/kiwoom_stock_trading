import sys
import time
from PyQt5.QtWidgets import QApplication
from kiwoom_api import Kiwoom

def main():
    app = QApplication(sys.argv)
    kiwoom = Kiwoom()
    print("Connecting to Kiwoom API...")
    kiwoom.comm_connect()
    
    # 1. Get Accounts
    accounts = kiwoom.get_login_info("ACCNO")
    if not accounts:
        print("No accounts found.")
        sys.exit(0)
    
    # Remove empty strings if any
    accounts = [acc for acc in accounts if acc]
    account_no = accounts[0]
    print(f"Using Account: {account_no}")
    
    # 2. Display Status
    print("\n[Initial Account Status]")
    data = kiwoom.get_account_evaluation(account_no)
    if data:
        summary = data['summary']
        print(f"Total Buy: {summary['total_buy']:,} KRW")
        print(f"Total Eval: {summary['total_eval']:,} KRW")
        print(f"Total P/L: {summary['total_profit_loss']:,} KRW")
        print(f"Total Rate: {summary['total_rate']}%")
        print(f"Assets: {summary['estimated_assets']:,} KRW")
        print(f"Holdings: {len(data['holdings'])} items")
        for h in data['holdings']:
            print(f" - {h['name']}({h['code']}): {h['qty']} shares, Buy: {h['buy_price']:,}, Cur: {h['current_price']:,}, P/L: {h['eval_profit']:,} ({h['yield_rate']}%)")
    
    # 3. Buy 1 Share of Samsung Electronics (005930)
    print("\n[Sending Buy Order for Samsung Electronics (005930)]")
    # Order Type 1: Buy
    # Price 0: Market Price
    # Code: 005930
    # Qty: 1
    kiwoom.send_order(1, account_no, "005930", 1, 0, "test_order_001")
    
    # Wait for order processing
    print("Waiting for 10 seconds for order execution...")
    time.sleep(10)
    
    # 4. Display Status Again
    print("\n[Final Account Status]")
    # We need to re-request data
    data = kiwoom.get_account_evaluation(account_no)
    if data:
        summary = data['summary']
        print(f"Total Buy: {summary['total_buy']:,} KRW")
        print(f"Total Eval: {summary['total_eval']:,} KRW")
        print(f"Total P/L: {summary['total_profit_loss']:,} KRW")
        print(f"Total Rate: {summary['total_rate']}%")
        print(f"Assets: {summary['estimated_assets']:,} KRW")
        print(f"Holdings: {len(data['holdings'])} items")
        for h in data['holdings']:
            print(f" - {h['name']}({h['code']}): {h['qty']} shares, Buy: {h['buy_price']:,}, Cur: {h['current_price']:,}, P/L: {h['eval_profit']:,} ({h['yield_rate']}%)")

if __name__ == "__main__":
    main()
