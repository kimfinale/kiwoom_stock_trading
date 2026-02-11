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
    
    print(f"Accounts found: {accounts}")
    
    # Select account logic matching run.py (accounts[1] if available)
    if len(accounts) >= 2:
        account_no = accounts[1]
        print(f"Selecting second account (matching run.py): {account_no}")
    else:
        account_no = accounts[0]
        print(f"Only one account found, selecting: {account_no}")
        
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
    
    
    # Configuration
    TARGET_CODE = "005930" # Samsung Electronics
    TARGET_TOTAL_INVESTMENT = 4000000 # 4 Million KRW
    BUY_INTERVAL = 300 # 5 Minutes (in seconds)
    
    print(f"\n[Starting Recurring Buy Strategy]")
    print(f"Target Stock: {TARGET_CODE}")
    print(f"Target Total Investment: {TARGET_TOTAL_INVESTMENT:,} KRW")
    print(f"Buy Interval: {BUY_INTERVAL} seconds")

    try:
        while True:
            print("\n--------------------------------------------------")
            print(f"Checking Account Status at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 1. Update Account Data
            data = kiwoom.get_account_evaluation(account_no)
            if not data:
                print("Failed to get account data. Retrying in 10 seconds...")
                time.sleep(10)
                continue
                
            summary = data['summary']
            holdings = data['holdings']
            
            # 2. Check current holdings of target stock
            current_holding_value = 0
            current_qty = 0
            current_price = 0
            
            # Find target stock in holdings
            target_holding = None
            for h in holdings:
                if h['code'] == TARGET_CODE:
                    target_holding = h
                    break
            
            if target_holding:
                current_qty = target_holding['qty']
                current_holding_value = target_holding['eval_profit'] + target_holding['buy_price'] * current_qty # Evaluation Value? No, usually 'Current Price * Qty' is current value. 
                # Let's use clean calculation: Current Price * Qty
                current_price = target_holding['current_price']
                current_holding_value = current_price * current_qty
                print(f"Current Holdings: {current_qty} shares, Value: {current_holding_value:,} KRW")
            else:
                # If not holding, get current price from market
                print("Target stock not in holdings. Fetching current price...")
                price_info = kiwoom.get_current_price(TARGET_CODE)
                if price_info:
                    current_price = abs(price_info['price']) # Price comes as abs value
                else:
                    print("Failed to get price info.")
                    time.sleep(10)
                    continue

            # 3. Decision Logic
            if current_holding_value >= TARGET_TOTAL_INVESTMENT:
                print(f"Target investment reached ({current_holding_value:,} KRW >= {TARGET_TOTAL_INVESTMENT:,} KRW). stopping script.")
                break
            
            # Buy 1 share
            print(f"Target not reached. Buying 1 share of {TARGET_CODE}...")
            # Order Type 1: Buy, Price 0: Market Price
            kiwoom.send_order(1, account_no, TARGET_CODE, 1, 0, "")
            
            # 4. Wait
            print(f"Waiting {BUY_INTERVAL} seconds for next check...")
            time.sleep(BUY_INTERVAL)

    except KeyboardInterrupt:
        print("\nScript stopped by user.")

if __name__ == "__main__":
    main()

