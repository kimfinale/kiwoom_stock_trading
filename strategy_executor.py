import datetime
from state_manager import StateManager
# from kiwoom_api import Kiwoom # Injected dependency

class StrategyExecutor:
    def __init__(self, kiwoom, state_manager, config):
        self.kiwoom = kiwoom
        self.state = state_manager
        self.config = config
        self.is_dry_run = config.get("dry_run", True)
        
        # Parameters
        self.P = config["strategy"]["P"]
        self.D = config["strategy"]["D"]
        self.R = config["strategy"]["R"]
        
        self.allocation = config["strategy"]["allocation_ratio"]
        self.total_capital = config["total_capital"]

    def execute_step(self):
        print(f"\n--- Execution Step: {datetime.datetime.now()} ---")
        
        # For each stock in config
        for stock in self.config["stocks"]:
            code = stock["code"]
            name = stock["name"]
            
            # 1. Get Current Price
            if self.is_dry_run:
                # Mock price for testing or fetch real price but don't trade
                current_data = self.kiwoom.get_current_price(code) # This works in dry run too if connected
                current_price = current_data['price']
                if current_price == 0: 
                    print(f"Invalid price 0 for {name}. Skipping.")
                    continue
            else:
                current_data = self.kiwoom.get_current_price(code)
                current_price = current_data['price']
            
            print(f"Processing {name} ({code}) - Price: {current_price}")
            
            # 2. Process Account 1
            self.process_account_1(code, current_price)
            
            # 3. Process Account 2+
            self.process_account_2_plus(code, current_price)
            
    def process_account_1(self, code, current_price):
        acc_alias = "Account1"
        account_no = self.config["accounts"][acc_alias]  # Map to real acc no
        
        # --- Sell Logic ---
        # Check holdings for Acc 1
        holdings = self.state.get_open_positions(acc_alias, code)
        for h in holdings:
            buy_price = h["price"]
            target_price = buy_price * (1 + self.P)
            
            if current_price >= target_price:
                print(f"[{acc_alias}] SELL Signal: Current {current_price} >= Target {target_price} (Buy {buy_price})")
                self._execute_trade(acc_alias, code, "SELL", current_price, h["qty"], h_index=self.state.state["trades"].index(h))
        
        # --- Buy Logic ---
        # Buy 1 share every step (interval is handled by scheduler)
        # Check buffer/balance
        allocated_amt = self.total_capital * self.allocation[acc_alias]
        used_amt = sum([t["price"] * t["qty"] for t in self.state.get_account_history(acc_alias) if t["action"] == "BUY"])
        
        if used_amt + current_price <= allocated_amt:
             print(f"[{acc_alias}] BUY Signal: Price {current_price}")
             self._execute_trade(acc_alias, code, "BUY", current_price, 1)
        else:
            print(f"[{acc_alias}] Skip Buy: Budget Exceeded ({used_amt}/{allocated_amt})")

    def process_account_2_plus(self, code, current_price):
        # Account 2 Logic: Based on Batch Average of Acc 1
        
        # 1. Identify Batches from Acc 1 History
        acc1_history = [t for t in self.state.get_account_history("Account1") 
                        if t["code"] == code and t["action"] == "BUY"]
        
        batch_size = 4
        num_batches = len(acc1_history) // batch_size
        
        # Iterate through batches logic
        # Check Acc 2 history to see which batch is next
        acc2_history = [t for t in self.state.get_account_history("Account2") 
                        if t["code"] == code and t["action"] == "BUY"]
        
        next_batch_idx = len(acc2_history)
        
        if next_batch_idx < num_batches:
            # We have a new batch to consider
            batch_slice = acc1_history[next_batch_idx*batch_size : (next_batch_idx+1)*batch_size]
            avg_price_at_purchase = sum(t["price"] for t in batch_slice) / batch_size
            
            # Current Buy Condition for Acc 2
            target_buy_price = avg_price_at_purchase * (1 - self.D)
            target_sell_price = avg_price_at_purchase * (1 - self.D) * (1 + self.R)
            
            print(f"[Account2] Batch {next_batch_idx+1}: Avg {avg_price_at_purchase:.0f}, Target Buy <= {target_buy_price:.0f}")
            
            if current_price <= target_buy_price:
                 print(f"[Account2] BUY Signal: Price {current_price} <= {target_buy_price}")
                 
                 # Logic for Acc 2, Acc 3, Acc 4, Acc 5
                 for i in range(2, 6):
                     acc_name = f"Account{i}" # Assuming keys are Account2, ..., Account5
                     
                     # Check Budget
                     allocated_amt = self.total_capital * self.allocation[acc_name]
                     used_amt = sum([t["price"] * t["qty"] for t in self.state.get_account_history(acc_name) 
                                    if t["action"] == "BUY"])
                                    
                     if used_amt + current_price <= allocated_amt:
                         self._execute_trade(acc_name, code, "BUY", current_price, 1, 
                                           batch_ref=next_batch_idx, 
                                           target_sell_price=target_sell_price)
                     else:
                         print(f"[{acc_name}] Skip Buy: Budget Exceeded")

        # --- Sell Logic for Acc 2+ ---
        for i in range(2, 6):
            acc_name = f"Account{i}"
            holdings = self.state.get_open_positions(acc_name, code)
            
            for h in holdings:
                target_sell_price = h.get("target_sell_price")
                
                # If target_sell_price is missing (legacy?), try to infer or skip
                if not target_sell_price:
                    continue
                    
                if current_price >= target_sell_price:
                    print(f"[{acc_name}] SELL Signal: {current_price} >= {target_sell_price}")
                    self._execute_trade(acc_name, code, "SELL", current_price, h["qty"], h_index=self.state.state["trades"].index(h))


    def _execute_trade(self, account_alias, code, action, price, qty, h_index=None, batch_ref=None, target_sell_price=None):
        trade_meta = {}
        if batch_ref is not None:
            trade_meta['batch_ref'] = batch_ref
        if target_sell_price is not None:
            trade_meta['target_sell_price'] = target_sell_price
            
        if self.is_dry_run:
            print(f"___DRY RUN___: {action} {qty} of {code} at {price} in {account_alias} {trade_meta}")
            
            if action == "BUY":
                self.state.record_trade(account_alias, code, action, price, qty, **trade_meta)
            elif action == "SELL":
                sell_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.state.close_position(h_index, price, sell_time)
        else:
            # Real Trade
            account_no = self.config["accounts"][account_alias]
            order_type = 1 if action == "BUY" else 2
            
            # Send Order
            if self.kiwoom.send_order(order_type, account_no, code, qty, 0): # Market Price
                if action == "BUY":
                     self.state.record_trade(account_alias, code, action, price, qty, **trade_meta)
                elif action == "SELL":
                     sell_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                     self.state.close_position(h_index, price, sell_time)

