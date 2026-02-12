import datetime
import json
import os

class Account:
    def __init__(self, account_id, principal, stock_code=None, strategy_config=None, balance=None, holdings=None, history=None, performance_log=None):
        self.account_id = account_id
        self.principal = principal
        self.stock_code = stock_code
        self.balance = balance if balance is not None else principal
        self.strategy_config = strategy_config if strategy_config else {}
        self.holdings = holdings if holdings else {}  # code -> {qty, avg_price, ...}
        self.history = history if history else []     # List of trade dicts
        self.performance_log = performance_log if performance_log else [] # List of snapshots

    def buy(self, code, price, qty, timestamp=None, **kwargs):
        cost = price * qty
        if self.balance < cost:
            return False, "Insufficient balance"

        if timestamp is None:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update Balance
        self.balance -= cost

        # Update Holdings
        if code not in self.holdings:
            self.holdings[code] = {"qty": 0, "avg_price": 0, "total_cost": 0}
        
        current_holding = self.holdings[code]
        new_qty = current_holding["qty"] + qty
        new_total_cost = current_holding["total_cost"] + cost
        new_avg_price = new_total_cost / new_qty if new_qty > 0 else 0

        self.holdings[code] = {
            "qty": new_qty,
            "avg_price": new_avg_price,
            "total_cost": new_total_cost
        }

        # Record History
        trade = {
            "action": "BUY",
            "code": code,
            "price": price,
            "qty": qty,
            "time": timestamp,
            "balance_after": self.balance
        }
        trade.update(kwargs)
        self.history.append(trade)

        return True, "Buy successful"

    def sell(self, code, price, qty, timestamp=None, **kwargs):
        if code not in self.holdings or self.holdings[code]["qty"] < qty:
            return False, "Insufficient holdings"

        if timestamp is None:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        proceeds = price * qty
        
        # Update Balance
        self.balance += proceeds

        # Update Holdings
        current_holding = self.holdings[code]
        avg_price = current_holding["avg_price"]
        
        # Calculate PnL for this specific trade (FIFO/Avg logic simplified to Avg)
        trade_pnl = (price - avg_price) * qty
        
        new_qty = current_holding["qty"] - qty
        new_total_cost = current_holding["total_cost"] - (avg_price * qty) # Reducing cost proportionally

        if new_qty == 0:
            del self.holdings[code]
        else:
            self.holdings[code] = {
                "qty": new_qty,
                "avg_price": avg_price, # Avg price doesn't change on sell
                "total_cost": new_total_cost
            }

        # Record History
        trade = {
            "action": "SELL",
            "code": code,
            "price": price,
            "qty": qty,
            "time": timestamp,
            "pnl": trade_pnl,
            "balance_after": self.balance
        }
        trade.update(kwargs)
        self.history.append(trade)

        return True, "Sell successful"

    def get_total_value(self, current_prices):
        """
        Calculate total account value (Cash + Stock Value).
        current_prices: dict {code: price}
        """
        stock_value = 0
        for code, holding in self.holdings.items():
            price = current_prices.get(code, holding["avg_price"]) # Fallback to avg_price if current not available
            stock_value += price * holding["qty"]
        
        return self.balance + stock_value

    def update_snapshot(self, current_prices, timestamp=None):
        if timestamp is None:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        total_value = self.get_total_value(current_prices)
        pnl = total_value - self.principal
        pnl_rate = (pnl / self.principal) * 100 if self.principal > 0 else 0
        
        snapshot = {
            "time": timestamp,
            "total_value": total_value,
            "balance": self.balance,
            "pnl": pnl,
            "pnl_rate": pnl_rate,
            "holdings_count": len(self.holdings)
        }
        
        # Keep last 60 days of 5 min intervals = 12 * 24 * 60 = 17280 entries max
        # For now just append, we can prune later
        self.performance_log.append(snapshot)
        
        # Pruning logic could be added here
        
        return snapshot

    def to_dict(self):
        return {
            "account_id": self.account_id,
            "principal": self.principal,
            "stock_code": self.stock_code,
            "balance": self.balance,
            "strategy_config": self.strategy_config,
            "holdings": self.holdings,
            "history": self.history,
            "performance_log": self.performance_log
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            account_id=data["account_id"],
            principal=data["principal"],
            stock_code=data.get("stock_code"),
            strategy_config=data.get("strategy_config"),
            balance=data.get("balance"),
            holdings=data.get("holdings"),
            history=data.get("history"),
            performance_log=data.get("performance_log")
        )


def create_split_account(total_money, num_sub_accounts, proportions, strategy_configs, stock_code=None):
    """
    Factory function to create multiple Account objects.
    
    Args:
        total_money (float): Total capital to split.
        num_sub_accounts (int): Number of accounts to create.
        proportions (list): List of floats summing to 1.0.
        strategy_configs (list): List of dicts specific to each account.
        stock_code (str, optional): The stock code assigned to these accounts.
        
    Returns:
        list: List of Account objects.
    """
    if len(proportions) != num_sub_accounts:
        raise ValueError("Length of proportions must match num_sub_accounts")
    
    if len(strategy_configs) != num_sub_accounts:
        raise ValueError("Length of strategy_configs must match num_sub_accounts")

    accounts = []
    
    for i in range(num_sub_accounts):
        acc_cfg = strategy_configs[i]
        acc_id = acc_cfg.get("account_id", f"SubAcc_{i+1}")
        # Use provided stock_code or try to find it in config
        s_code = stock_code if stock_code else acc_cfg.get("stock_code")
        
        ratio = proportions[i]
        allocated_capital = int(total_money * ratio) 
        
        acc = Account(
            account_id=acc_id,
            principal=allocated_capital,
            stock_code=s_code,
            strategy_config=acc_cfg
        )
        accounts.append(acc)
        
    return accounts

def save_accounts(accounts, filename="trade_state.json"):
    data = [acc.to_dict() for acc in accounts]
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_accounts(filename="trade_state.json"):
    if not os.path.exists(filename):
        return None
    
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    return [Account.from_dict(d) for d in data]
