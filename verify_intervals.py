import time
import json
import io
from datetime import datetime
from unittest.mock import MagicMock

# Mock classes
class MockKiwoom:
    def __init__(self):
        self.tr_data = None
    def comm_connect(self):
        print("Mock Kiwoom connected")
    def get_login_info(self, tag):
        return ["8119599511"]
    def get_account_evaluation(self, acc):
        return {'summary': {'estimated_assets': 1000000}, 'holdings': []}
    def get_current_price(self, code):
        return {'price': 70000}
    def send_order(*args):
        return True

class MockAccount:
    def __init__(self, account_id, balance=1000000):
        self.account_id = account_id
        self.balance = balance
        self.holdings = {}
        self.performance_log = []
        self.history = []
    def update_snapshot(self, prices, timestamp=None):
        pass
    def buy(self, code, price, qty, **kwargs):
        print(f"Mock Buy: {qty} {code}")
        return True, "Success"

# Mock Imports in real_time_trader if we were importing, 
# but here we will just replicate the MAIN LOOP logic to test it.

def verify_intervals():
    print("Starting Interval Verification...")
    
    # Fast Intervals for Testing
    check_interval_min = 0.1  # 6 seconds
    leader_interval_min = 0.2 # 12 seconds
    dashboard_interval_min = 0.3 # 18 seconds
    
    print(f"Test Intervals: Check={check_interval_min*60}s, Leader={leader_interval_min*60}s, Dash={dashboard_interval_min*60}s")

    now = time.time()
    last_price_check_time = 0
    last_leader_buy_time = 0
    last_dashboard_time = 0
    
    iteration = 0
    start_time = now
    
    # Mock Executor
    executor = MagicMock()
    
    while time.time() - start_time < 25: # Run for 25 seconds
        time.sleep(1)
        now = time.time()
        
        # 1. Price Check (Base)
        if now - last_price_check_time >= check_interval_min * 60:
            iteration += 1
            last_price_check_time = now
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Tick #{iteration} (Check)")
            
            allow_leader_buy = False
            if now - last_leader_buy_time >= leader_interval_min * 60:
                allow_leader_buy = True
                last_leader_buy_time = now
                print(f"  ⚡ LEADER BUY ENABLED")
            
            executor.execute_step(allow_leader_buy=allow_leader_buy)
            
        # 2. Dashboard
        if now - last_dashboard_time >= dashboard_interval_min * 60:
            last_dashboard_time = now
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 DASHBOARD SYNC")

    print("Verification Completed.")

if __name__ == "__main__":
    verify_intervals()
