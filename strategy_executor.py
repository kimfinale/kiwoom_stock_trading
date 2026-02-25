import datetime
import random
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
        self._leader_last_buy_date = {}  # strategy_id -> "YYYY-MM-DD"

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
            if not self.is_dry_run:
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
            self.process_leader(leader_acc_cfg, code, current_price, allow_leader_buy, strategy_id=s_id)

        # 3. Process Followers
        if leader_acc_cfg and followers_cfg:
             self.process_followers(leader_acc_cfg, followers_cfg, code, current_price)

    def process_leader(self, acc_config, code, current_price, allow_buy=True, strategy_id=None):
        acc_id = acc_config["account_id"]
        if acc_id not in self.accounts:
            print(f"  ⚠️  Account {acc_id} not found in state.")
            return

        account = self.accounts[acc_id]
        params = acc_config["params"]
        target_profit = params.get("target_profit", 0.1)

        # --- Sell Logic ---
        if code in account.holdings:
             holding = account.holdings[code]
             qty = holding["qty"]
             avg_price = holding["avg_price"]

             if qty > 0:
                 target_price = avg_price * (1 + target_profit)

                 if current_price >= target_price:
                     print(f"  [{acc_id}] SELL Signal: Current {current_price} >= Target {target_price:.0f} (Avg {avg_price:.0f})")
                     pre_sell_balance = account.balance
                     self._execute_trade(account, code, "SELL", current_price, qty)
                     # Do not replenish leader balance — cumulative spending is capped by initial allocation
                     account.balance = pre_sell_balance

        # --- Buy Logic ---
        if not allow_buy:
            return

        # Frequency check: once per day per strategy
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        if strategy_id and self._leader_last_buy_date.get(strategy_id) == today_str:
            return

        # Price range check
        price_lower = params.get("price_lower_limit", 0)
        price_upper = params.get("price_upper_limit", None)

        if current_price < price_lower:
            print(f"  [{acc_id}] Skip Buy: Price {current_price:,} < lower limit {price_lower:,}")
            return
        if price_upper is not None and current_price > price_upper:
            print(f"  [{acc_id}] Skip Buy: Price {current_price:,} > upper limit {price_upper:,}")
            return

        # Determine quantity
        buy_amount = params.get("buy_amount", 200000)
        buy_quantity = params.get("buy_quantity")

        if buy_quantity is not None:
            qty_to_buy = buy_quantity
        else:
            qty_to_buy = int(buy_amount // current_price)

        if qty_to_buy > 0:
            total_cost = qty_to_buy * current_price
            if account.balance >= total_cost:
                 print(f"  [{acc_id}] BUY Signal: Price {current_price}, Qty {qty_to_buy} (Total: {total_cost:,.0f} KRW, Bal: {account.balance:,.0f})")
                 self._execute_trade(account, code, "BUY", current_price, qty_to_buy)
                 if strategy_id:
                     self._leader_last_buy_date[strategy_id] = today_str

    def process_followers(self, leader_cfg, followers_cfg, code, current_price):
        leader_id = leader_cfg["account_id"]
        if leader_id not in self.accounts: return
        leader_acc = self.accounts[leader_id]

        leader_ratio = leader_cfg.get("ratio", 0.40)
        leader_buy_amount = leader_cfg["params"].get("buy_amount", 200000)

        # Get Leader History (Batches)
        leader_buys = [t for t in leader_acc.history
                        if t["code"] == code and t["action"] == "BUY"]

        num_batches = len(leader_buys)

        for acc_config in followers_cfg:
            acc_id = acc_config["account_id"]
            if acc_id not in self.accounts: continue

            account = self.accounts[acc_id]
            params = acc_config["params"]
            dip_threshold = params.get("dip", 0.01)
            target_profit = params.get("target_profit", 0.03)
            follower_ratio = acc_config.get("ratio", 0.15)

            # --- Per-Lot Sell Logic (process sells first so cash is available for buys) ---
            open_lots = [t for t in account.history
                         if t["code"] == code and t["action"] == "BUY" and t.get("status") == "OPEN"]

            for lot in open_lots:
                target_sell = lot.get("target_sell_price")
                if target_sell and current_price >= target_sell:
                    lot_qty = lot["qty"]
                    print(f"  [{acc_id}] SELL Signal (Lot batch {lot.get('batch_ref')}): "
                          f"{current_price} >= {target_sell:.0f} (Buy@ {lot['price']:,}), Qty {lot_qty}")
                    self._execute_trade(account, code, "SELL", current_price, lot_qty,
                                        batch_ref=lot.get("batch_ref"))
                    lot["status"] = "CLOSED"

            # --- Fallback: aggregate sell for legacy positions without status field ---
            remaining_open = [t for t in account.history
                              if t["code"] == code and t["action"] == "BUY" and t.get("status") == "OPEN"]
            if (code in account.holdings and account.holdings[code]["qty"] > 0
                    and not remaining_open):
                avg_p = account.holdings[code]["avg_price"]
                target_price = avg_p * (1 + target_profit)
                if current_price >= target_price:
                    qty = account.holdings[code]["qty"]
                    print(f"  [{acc_id}] SELL Signal (legacy aggregate): "
                          f"{current_price} >= {target_price:.0f} (Avg {avg_p:.0f}), Qty {qty}")
                    self._execute_trade(account, code, "SELL", current_price, qty)

            # --- Self-Cycling Buy Logic ---
            # Which leader batches already have an OPEN lot?
            open_batch_refs = {t.get("batch_ref") for t in account.history
                               if t["code"] == code and t["action"] == "BUY" and t.get("status") == "OPEN"}

            for batch_idx in range(num_batches):
                if batch_idx in open_batch_refs:
                    continue  # Already have an open lot for this batch

                leader_batch = leader_buys[batch_idx]
                leader_batch_price = leader_batch["price"]
                target_buy_price = leader_batch_price * (1 - dip_threshold)

                if current_price <= target_buy_price:
                    # Compute proportional qty with stochastic rounding
                    follower_buy_amount = leader_buy_amount * (follower_ratio / leader_ratio)
                    exact_qty = follower_buy_amount / current_price
                    base_qty = int(exact_qty)
                    fractional = exact_qty - base_qty
                    qty_to_buy = base_qty + (1 if random.random() < fractional else 0)

                    if qty_to_buy <= 0:
                        print(f"  [{acc_id}] Skip Buy: Stochastic round -> 0 shares "
                              f"(amount {follower_buy_amount:,.0f} KRW)")
                        break  # Still counts as this tick's buy attempt

                    total_cost = qty_to_buy * current_price
                    my_target_sell = current_price * (1 + target_profit)

                    print(f"  [{acc_id}] BUY Signal (batch {batch_idx}): "
                          f"{current_price} <= {target_buy_price:.0f} "
                          f"(Dip {dip_threshold*100}% from leader {leader_batch_price:,}), "
                          f"Qty {qty_to_buy} ({follower_buy_amount:,.0f} KRW)")

                    if account.balance >= total_cost:
                        self._execute_trade(account, code, "BUY", current_price, qty_to_buy,
                                            batch_ref=batch_idx,
                                            target_sell_price=my_target_sell,
                                            status="OPEN")
                    else:
                        print(f"  [{acc_id}] Skip Buy: Insufficient Budget "
                              f"({account.balance:,.0f} < {total_cost:,.0f})")
                    break  # One buy per tick per follower


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



