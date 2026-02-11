import json
import os
import datetime

class StateManager:
    def __init__(self, filename="trade_state.json"):
        self.filename = filename
        self.state = {
            "accounts": {},      # Defined mapping of Account# -> Actual AccNo
            "trades": [],        # History of completed trades or active holdings
            "batches": {},       # Track batches for Acc > 1 logic
            "last_check_time": None
        }
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)
            except Exception as e:
                print(f"Failed to load state: {e}. Starting fresh.")
        else:
            print("No existing state found. Starting fresh.")

    def save(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, indent=4, ensure_ascii=False)

    def record_trade(self, account_alias, code, action, price, qty, timestamp=None, **kwargs):
        if timestamp is None:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        trade = {
            "account": account_alias,
            "code": code,
            "action": action, # 'BUY', 'SELL'
            "price": price,
            "qty": qty,
            "time": timestamp,
            "status": "OPEN" if action == 'BUY' else "CLOSED"
        }
        trade.update(kwargs)
        
        # If BUY, add to tracked holdings
        # If SELL, find corresponding BUY and mark CLOSED (FIFO or specific ID matching would be better, but simplified for now)
        
        self.state["trades"].append(trade)
        self.save()

    def get_open_positions(self, account_alias, code):
        # Return list of BUY trades that haven't been SOLD yet
        # Logic: Simple counter matching for now
        buys = [t for t in self.state["trades"] 
                if t["account"] == account_alias and t["code"] == code and t["action"] == "BUY" and t["status"] == "OPEN"]
        return buys

    def close_position(self, trade_index, sell_price, sell_time):
        if 0 <= trade_index < len(self.state["trades"]):
            self.state["trades"][trade_index]["status"] = "CLOSED"
            self.state["trades"][trade_index]["sell_price"] = sell_price
            self.state["trades"][trade_index]["sell_time"] = sell_time
            self.save()

    def get_account_history(self, account_alias):
        return [t for t in self.state["trades"] if t["account"] == account_alias]

if __name__ == "__main__":
    # Test
    sm = StateManager("test_state.json")
    sm.record_trade("Account1", "005930", "BUY", 70000, 1)
    print(sm.get_open_positions("Account1", "005930"))
