import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from simulate_algorithm import generate_stock_price_series

class Strategy:
    def __init__(self, name, initial_cash=1_000_000):
        self.name = name
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.shares = 0
        self.history = [] # List of dicts: {'step': t, 'value': val}
        self.trades = []  # List of dicts: {'step': t, 'type': 'BUY'/'SELL', 'price': p, 'shares': s}

    def get_portfolio_value(self, current_price):
        return self.cash + (self.shares * current_price)
    
    def log_value(self, step, current_price):
        val = self.get_portfolio_value(current_price)
        self.history.append({'step': step, 'value': val})
        return val

    def buy(self, step, price, amount=None):
        if self.cash <= 0: return False
        max_shares = int(self.cash // price)
        if max_shares == 0: return False
        qty = max_shares if amount is None else min(max_shares, amount)
        cost = qty * price
        self.cash -= cost
        self.shares += qty
        self.trades.append({'step': step, 'type': 'BUY', 'price': price, 'shares': qty})
        return True

    def sell(self, step, price, amount=None):
        if self.shares <= 0: return False
        qty = self.shares if amount is None else min(self.shares, amount)
        revenue = qty * price
        self.cash += revenue
        self.shares -= qty
        self.trades.append({'step': step, 'type': 'SELL', 'price': price, 'shares': qty})
        return True

    def prepare(self, prices_series):
        """Optional: Pre-calculate indicators on full history"""
        pass

    def on_data(self, step, price):
        pass


class BuyAndHoldStrategy(Strategy):
    def __init__(self):
        super().__init__("Buy & Hold")

    def on_data(self, step, price):
        if step == 0:
            self.buy(step, price)


class BollingerBandsStrategy(Strategy):
    def __init__(self, window=20, num_std=2):
        super().__init__("Bollinger Bands")
        self.window = window
        self.num_std = num_std
        self.upper_band = None
        self.lower_band = None

    def prepare(self, prices_series):
        # Vectorized calculation
        rolling = prices_series.rolling(window=self.window)
        mean = rolling.mean()
        std = rolling.std()
        self.upper_band = mean + (self.num_std * std)
        self.lower_band = mean - (self.num_std * std)

    def on_data(self, step, price):
        if step < self.window: return # Not enough data
        
        # Look up pre-calculated values
        # Because step matches the index in the series
        u = self.upper_band.iloc[step]
        l = self.lower_band.iloc[step]
        
        if pd.isna(u): return

        if price < l:
            if self.cash > 0: self.buy(step, price)
        elif price > u:
            if self.shares > 0: self.sell(step, price)


class GoldenCrossStrategy(Strategy):
    def __init__(self, short_window=50, long_window=200):
        super().__init__("Golden Cross")
        self.short_window = short_window
        self.long_window = long_window
        self.short_ma = None
        self.long_ma = None
        self.position = 0

    def prepare(self, prices_series):
        self.short_ma = prices_series.rolling(window=self.short_window).mean()
        self.long_ma = prices_series.rolling(window=self.long_window).mean()

    def on_data(self, step, price):
        if step < self.long_window: return
        
        s_ma = self.short_ma.iloc[step]
        l_ma = self.long_ma.iloc[step]

        if pd.isna(s_ma) or pd.isna(l_ma): return

        if s_ma > l_ma and self.position == 0:
            if self.buy(step, price): self.position = 1
        elif s_ma < l_ma and self.position == 1:
            if self.sell(step, price): self.position = 0


class UserAccount:
    def __init__(self, name, initial_cash, index, r=0.01, s=0.02):
        self.name = name
        self.cash = initial_cash
        self.shares = 0
        self.params = {'index': index, 'r': r, 's': s}
        self.target_sell_price = 0

    def get_value(self, price):
        return self.cash + (self.shares * price)

class UserCurrentStrategy(Strategy):
    def __init__(self, r=0.01, s=0.02):
        super().__init__("User Strategy")
        self.r = r
        self.s = s
        self.accounts = []
        self.accounts.append(UserAccount("Acc1", self.initial_cash * 0.4, 1, r, s))
        for i in range(2, 8):
            self.accounts.append(UserAccount(f"Acc{i}", self.initial_cash * 0.1, i, r, s))
        self.current_ref_price = 0

    def get_portfolio_value(self, current_price):
        return sum(acc.get_value(current_price) for acc in self.accounts)

    def on_data(self, step, price):
        if step == 0:
            self.current_ref_price = price
            self._acc_buy(self.accounts[0], price, step, ref_x=price)
            # Other accounts logic for step 0?
            # Assuming other accounts don't buy at step 0 unless condition met?
            # Original code forced Acc1 buy at step 0.
            return

        # Acc 1
        acc1 = self.accounts[0]
        if acc1.shares > 0:
            if price >= acc1.target_sell_price:
                self._acc_sell(acc1, price, step)
                self._acc_buy(acc1, price, step, ref_x=price)
                self.current_ref_price = price
        elif acc1.shares == 0 and acc1.cash > 0:
             self._acc_buy(acc1, price, step, ref_x=price)
             if acc1.shares > 0: self.current_ref_price = price

        # Acc 2..7
        for acc in self.accounts[1:]:
            k = acc.params['index']
            trigger_price = (1 - (k - 1) * self.r) * self.current_ref_price
            
            if acc.shares == 0 and acc.cash > 0:
                if price <= trigger_price:
                    self._acc_buy(acc, price, step, ref_x=self.current_ref_price)
            
            if acc.shares > 0 and price >= acc.target_sell_price:
                self._acc_sell(acc, price, step)

    def _acc_buy(self, acc, price, step, ref_x=None):
        max_shares = int(acc.cash // price)
        if max_shares > 0:
            cost = max_shares * price
            acc.cash -= cost
            acc.shares += max_shares
            
            if acc.params['index'] == 1:
                acc.target_sell_price = price * 1.10
            else:
                k = acc.params['index']
                if ref_x:
                    trigger_level = (1 - (k - 1) * self.r) * ref_x
                    acc.target_sell_price = trigger_level * (1 + self.s)
                else:
                    acc.target_sell_price = price * (1 + self.s)
            
            self.trades.append({'step': step, 'type': 'BUY', 'price': price, 'shares': max_shares, 'account': acc.name})

    def _acc_sell(self, acc, price, step):
        revenue = acc.shares * price
        acc.cash += revenue
        acc.shares = 0
        self.trades.append({'step': step, 'type': 'SELL', 'price': price, 'shares': 0, 'account': acc.name})


def run_comparison():
    print("Generating price data...")
    prices = generate_stock_price_series(start_price=10000, mu=0.05, sigma=0.3)
    prices_series = pd.Series(prices)
    
    print(f"Data Length: {len(prices)}")

    # Init Strategies
    # Note: 5-min intervals. 1 day = 12 * 24 = 288 steps (assuming 24h as per original prompt logic "365*24*12")
    # Actually prompt logic was 365*24*12 ?
    # In simulate_algorithm.py: n_steps = 365 * 24 * 12 = 105120
    # So 1 day ~ 288 steps.
    
    strategies = [
        BuyAndHoldStrategy(),
        BollingerBandsStrategy(window=20*288, num_std=2), # 20 days
        GoldenCrossStrategy(short_window=50*288, long_window=200*288), # 50 days, 200 days
        UserCurrentStrategy()
    ]

    print("Pre-calculating indicators...")
    for strat in strategies:
        strat.prepare(prices_series)
    
    print("Running simulation loop...")
    # Using simple loop
    for t, price in enumerate(prices):
        price = float(price)
        for strat in strategies:
            strat.on_data(t, price)
            strat.log_value(t, price)
            
        if t % 10000 == 0:
            print(f"Step {t}/{len(prices)}...")

    print("\n--- Strategy Comparison Results ---")
    plt.figure(figsize=(12, 6))
    
    for strat in strategies:
        final_val = strat.history[-1]['value']
        return_pct = ((final_val - 1_000_000) / 1_000_000) * 100
        n_trades = len(strat.trades)
        
        print(f"{strat.name:<20} | Return: {return_pct:>6.2f}% | Trades: {n_trades}")
        
        steps = [h['step'] for h in strat.history]
        vals = [h['value'] for h in strat.history]
        plt.plot(steps, vals, label=f"{strat.name} ({return_pct:.1f}%)")

    plt.title("Trading Strategy Comparison (1 Year Simulation)")
    plt.xlabel("Time Steps")
    plt.ylabel("Portfolio Value (KRW)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig('strategy_comparison.png')
    print("Saved comparison plot to strategy_comparison.png")

if __name__ == "__main__":
    run_comparison()
