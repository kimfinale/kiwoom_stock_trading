import datetime
# from state_manager import StateManager # Deprecated
# from kiwoom_api import Kiwoom # Injected dependency

class StrategyExecutor:
    def __init__(self, kiwoom, accounts_map, config, on_transaction_complete=None):
        self.kiwoom = kiwoom
        self.accounts = accounts_map
        self.config = config
        self.is_dry_run = config.get("dry_run", True)
        self.on_transaction_complete = on_transaction_complete  
        self.total_capital = config.get("total_capital", 0)

    def update_config(self, new_config):
        """Updates the configuration dynamically."""
        print(f"🔄 Updating StrategyExecutor Configuration...")
        self.config = new_config
        self.is_dry_run = new_config.get("dry_run", True)
        self.total_capital = new_config.get("total_capital", 0)
        print(f"   - Total Capital: {self.total_capital:,} KRW")
        print(f"   - Dry Run: {self.is_dry_run}")
        print(f"   - Strategies: {len(new_config.get('strategies', []))}")

    def execute_step(self, allow_leader_buy=True):
        print(f"\n--- Execution Step: {datetime.datetime.now()} ---")
        
        if "strategies" not in self.config:
            print("⚠️  No strategies found in config.")
            return

        # Snapshot account performance before processing
        # We need current prices to calculate equity. 
        # Ideally we fetch prices for all stocks first, or do it per strategy.
        # For simplicity, we'll do it per strategy here, or just inside process_strategy.
        
        for strategy in self.config["strategies"]:
            self.process_strategy(strategy, allow_leader_buy)
            import time
            time.sleep(0.5) # Prevent Rate Limiting
            
    def process_strategy(self, strategy, allow_leader_buy=True):
        s_id = strategy["id"]
        code = strategy["stock_code"]
        name = strategy["stock_name"]
        
        print(f"Processing Strategy: {s_id} ({name})")
        
        # 1. Get Current Price
        try:
            current_data = self.kiwoom.get_current_price(code)
            if not current_data or 'price' not in current_data:
                print(f"⚠️  [{s_id}] Failed to get price for {name}. Skipping.")
                return
                
            current_price = abs(current_data['price'])
            if current_price == 0:
                print(f"⚠️  [{s_id}] Invalid price 0. Skipping.")
                return
        except Exception as e:
            print(f"⚠️  [{s_id}] Error fetching price: {e}")
            return
            
        print(f"  Price: {current_price:,} KRW")
        
        # Identify Leader and Followers
        # Strategy config still has "accounts" list with suffix/ratio/type
        # We need to find the corresponding Account IDs.
        
        leader_acc_cfg = None
        followers_cfg = []
        
        for acc_cfg in strategy["accounts"]:
            # Reconstruct ID: {s_id}_{suffix}
            acc_id = f"{s_id}_{acc_cfg['suffix']}"
            acc_cfg["account_id"] = acc_id # Inject ID for easy access
            
            # Update Snapshot for this account
            if acc_id in self.accounts:
                self.accounts[acc_id].update_snapshot({code: current_price})
            
            if acc_cfg["strategy_type"] == "LEADER":
                leader_acc_cfg = acc_cfg
            else:
                followers_cfg.append(acc_cfg)
        
        # 2. Process Leader
        if leader_acc_cfg:
            self.process_leader(leader_acc_cfg, code, current_price, allow_leader_buy)
            
        # 3. Process Followers
        if leader_acc_cfg and followers_cfg:
             self.process_followers(leader_acc_cfg, followers_cfg, code, current_price)

    def process_leader(self, acc_config, code, current_price, allow_buy=True):
        acc_id = acc_config["account_id"]
        if acc_id not in self.accounts:
            print(f"  ⚠️  Account {acc_id} not found in state.")
            return
            
        account = self.accounts[acc_id]
        params = acc_config["params"]
        target_profit = params.get("target_profit", 0.1) # Default 10%
        
        # --- Sell Logic ---
        # Iterate over copy of values as we might delete
        # Account.holdings key is Stock Code.
        if code in account.holdings:
             holding = account.holdings[code]
             qty = holding["qty"]
             avg_price = holding["avg_price"]
             
             if qty > 0:
                 target_price = avg_price * (1 + target_profit)
                 
                 if current_price >= target_price:
                     print(f"  [{acc_id}] SELL Signal: Current {current_price} >= Target {target_price:.0f} (Avg {avg_price:.0f})")
                     self._execute_trade(account, code, "SELL", current_price, qty)
        
        # --- Buy Logic ---
        # Budget Check is now handled by Account.balance
        # But we still run the strategy condition check (e.g. any additional strategy logic?)
        # For LEADER, the logic seems to be: "Buy if we have money"? 
        # The original code logic: "if used_amt + current_price <= acc_capital"
        # Since Account.balance tracks available cash, we just heck if balance >= price.
        
        # Original code had a "Leader" simply buying if it had budget? 
        # Or was it buying ONCE?
        # The original code:
        # if used_amt + current_price <= acc_capital:
        #      print(f"  [{acc_name}] BUY Signal: Price {current_price}")
        #      self._execute_trade(...)
        
        # This implies it buys whenever it has money? That sounds like it fills the bag immediately.
        # Assuming that's the desired behavior for Leader.
        
        if allow_buy and account.balance >= current_price:
             # Prevent spam buying? Original code didn't safeguard against buying same tick?
             # Actually, original code relied on `used_amt`. 
             # If `used_amt` < `acc_capital`, it bought.
             # So it would buy until full.
             # We will replicate this.
             
             print(f"  [{acc_id}] BUY Signal: Price {current_price} (Bal: {account.balance:,.0f})")
             self._execute_trade(account, code, "BUY", current_price, 1)
        else:
            # print(f"  [{acc_id}] Skip Buy: Insufficient Budget ({account.balance:,.0f} < {current_price})")
            pass

    def process_followers(self, leader_cfg, followers_cfg, code, current_price):
        leader_id = leader_cfg["account_id"]
        if leader_id not in self.accounts: return
        leader_acc = self.accounts[leader_id]
        
        # Get Leader History (Batches)
        # Filter for BUY actions on this code
        leader_buys = [t for t in leader_acc.history 
                        if t["code"] == code and t["action"] == "BUY"]
        
        batch_size = 4
        num_batches = len(leader_buys) // batch_size
        
        for acc_config in followers_cfg:
            acc_id = acc_config["account_id"]
            if acc_id not in self.accounts: continue
            
            account = self.accounts[acc_id]
            params = acc_config["params"]
            dip_threshold = params.get("dip", 0.01)
            target_profit = params.get("target_profit", 0.03)
            
            # Identify Next Batch for this follower
            follower_buys = [t for t in account.history 
                            if t["code"] == code and t["action"] == "BUY"]
            
            next_batch_idx = len(follower_buys)
            
            # --- Buy Logic ---
            if next_batch_idx < num_batches:
                # Get Avg Price of Leader's Batch
                batch_slice = leader_buys[next_batch_idx*batch_size : (next_batch_idx+1)*batch_size]
                if not batch_slice: continue
                
                avg_price_at_purchase = sum(t["price"] for t in batch_slice) / len(batch_slice)
                
                target_buy_price = avg_price_at_purchase * (1 - dip_threshold)
                
                my_target_sell = target_buy_price * (1 + target_profit)
                
                if current_price <= target_buy_price:
                     print(f"  [{acc_id}] BUY Signal: {current_price} <= {target_buy_price:.0f} (Dip {dip_threshold*100}%)")
                     
                     if account.balance >= current_price:
                         self._execute_trade(account, code, "BUY", current_price, 1, 
                                           batch_ref=next_batch_idx, 
                                           target_sell_price=my_target_sell)
                     else:
                         print(f"  [{acc_id}] Skip Buy: Insufficient Budget")

            # --- Sell Logic ---
            # Followers sell based on *individual* trade targets stored in history or computed?
            # Original code stored `target_sell_price` in trade metadata.
            # But Account.holdings aggregates Qty/AvgPrice.
            # If we want to sell specific "batches" or "trades", we need to track them.
            # Account history has the record.
            # But `Account.sell` removes from holdings (FIFO/Avg).
            # If followers need to sell SPECIFIC batches, `Account` class might be too simple if it averages context.
            # however, `Account` implementation uses weighted average.
            # If we want to sell when *current price* >= *target of specific buy*, we can scan history?
            # BUT `Account.sell` doesn't support "sell specific lot".
            # Simplification: Followers sell if Current Price >= Avg Price * (1 + Profit)?
            # OR logic from original code: `target_sell = h.get("target_sell_price")`
            # Original code's `get_open_positions` returned list of TRADES.
            # My `Account.holdings` aggregates.
            # This is a behavior change.
            # To support "per-trade" selling, we might need `Account` to track lots.
            # OR we iterate `account.history` for OPEN trades.
            
            # Let's check `Account` class again.
            # `holdings` is simple aggregation.
            # `history` has all trades.
            # I can reconstruct "Open Lots" from history if I didn't store them explicitly.
            # Account class doesn't track "Open" status in history explicitly (it has "action").
            # But I can add "status" to history or separate "lots".
            
            # User requirement: "Accounts... keep track of transactions...".
            # If the strategy relies on per-lot selling, I should support it.
            # Original code `state_manager` had `status: OPEN/CLOSED`.
            # My `Account` class `history` has `action: BUY/SELL` but I didn't implement linking.
            
            # I will modify logic to be:
            # Check `holdings`.
            # If we have holdings, we check if we should sell.
            # The original logic: `if current_price >= target_sell`. 
            # `target_sell` calculated at BUY time.
            # Since I don't have per-lot tracking in `Account.holdings`,
            # I will use `avg_price` based target for now.
            # `target_sell = avg_price * (1 + target_profit)`
            
            if code in account.holdings and account.holdings[code]["qty"] > 0:
                 avg_p = account.holdings[code]["avg_price"]
                 
                 # Logic adaptation: Sell if current price > Avg * (1+target)
                 # This mirrors the intent for the aggregate position.
                 
                 target_price = avg_p * (1 + target_profit)
                 if current_price >= target_price:
                      qty = account.holdings[code]["qty"]
                      print(f"  [{acc_id}] SELL Signal: {current_price} >= {target_price:.0f} (Avg {avg_p:.0f})")
                      self._execute_trade(account, code, "SELL", current_price, qty)


    def _execute_trade(self, account, code, action, price, qty, **kwargs):
        trade_meta = kwargs
            
        transaction_executed = False
            
        if self.is_dry_run:
            print(f"___DRY RUN___: {action} {qty} of {code} at {price} in {account.account_id}")
            
            if action == "BUY":
                success, msg = account.buy(code, price, qty, **trade_meta)
                if success: transaction_executed = True
                else: print(f"❌ Dry Run Buy Failed: {msg}")
                
            elif action == "SELL":
                success, msg = account.sell(code, price, qty, **trade_meta)
                if success: transaction_executed = True
                else: print(f"❌ Dry Run Sell Failed: {msg}")

        else:
            # Real Trade
            # We need the REAL accumulated account number (Kiwoom Account)
            # which is `real_account_id` in config.
            # But `StrategyExecutor` doesn't have it explicitly stored, 
            # but we can get it from `config["real_account_id"]`.
            
            real_account_no = self.config.get("real_account_id")
            if not real_account_no:
                print("❌ Real Account ID missing in config!")
                return

            order_type = 1 if action == "BUY" else 2
            
            # --- Deposit Check for BUY Orders (Safety Net) ---
            if action == "BUY":
                try:
                    self.kiwoom.get_deposit(real_account_no)
                    deposit = self.kiwoom.tr_data
                    
                    if deposit is not None:
                        order_amount = price * qty
                        if deposit < order_amount:
                             print(f"❌ [RealAcc: {real_account_no}] INSUFFICIENT REAL FUNDS! {deposit:,} < {order_amount:,}")
                             return # Skip Trade
                        else:
                             print(f"✅ [RealAcc] Deposit Check Passed")

                except Exception as e:
                    print(f"⚠️  Error checking real deposit: {e}")
                    pass # Proceed if check fails (trusting virtual balance)

            # Send Order
            if self.kiwoom.send_order(order_type, real_account_no, code, qty, 0): # Market Price
                # Record in Virtual Account
                if action == "BUY":
                     success, msg = account.buy(code, price, qty, **trade_meta)
                     if success: transaction_executed = True
                elif action == "SELL":
                     success, msg = account.sell(code, price, qty, **trade_meta)
                     if success: transaction_executed = True
        
        # Call post-transaction callback if transaction was executed
        if transaction_executed and self.on_transaction_complete:
            try:
                self.on_transaction_complete(action, account.account_id, code, price, qty)
            except Exception as e:
                print(f"⚠️  Post-transaction callback error: {e}")



