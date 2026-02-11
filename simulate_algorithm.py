import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import data_loader as dl
import yfinance as yf
import FinanceDataReader as fdr
from datetime import timedelta
import itertools
import random
import os
import time

class Account:
    def __init__(self, name, initial_cash, account_index, d_param, r_param):
        self.name = name
        self.cash = initial_cash
        self.initial_capital = initial_cash
        self.lots = [] 
        self.params = {
            'index': account_index, 
            'd': d_param, 
            'r': r_param
        }
        self.trades = []
        self.total_invested = 0.0 
        
    @property
    def shares_held(self):
        return len(self.lots)
        
    @property
    def avg_price(self):
        if self.shares_held == 0:
            return 0.0
        return self.total_invested / self.shares_held

    def get_total_value(self, current_price):
        stock_val = self.shares_held * current_price
        return self.cash + stock_val

    def buy(self, price, time_idx, target_price):
        if self.cash <= 0:
            return False

        fee_rate = 0.00015
        effective_buy_price = price / (1 - fee_rate)

        cost = effective_buy_price
        if self.cash < cost:
            return False 

        self.cash -= cost
        self.lots.append({
            'price': price, 
            'cost': cost,   
            'time': time_idx,
            'target': target_price
        })
        self.total_invested += cost
        
        self.trades.append({
            'step': time_idx,
            'type': 'BUY',
            'price': price,
            'effective_price': cost,
            'shares': 1
        })
        return True

    def check_sell_lots(self, current_price, time_idx):
        if not self.lots:
            return 0
            
        fee_rate = 0.00015
        effective_sell_price = current_price * (1 - fee_rate)
        
        unsold_lots = []
        sold_count = 0
        revenue = 0.0
        
        for lot in self.lots:
            if current_price >= lot['target']:
                revenue += effective_sell_price
                sold_count += 1
                self.total_invested -= lot['cost'] 
                
                self.trades.append({
                    'step': time_idx,
                    'type': 'SELL',
                    'price': current_price,
                    'effective_price': effective_sell_price,
                    'shares': 1,
                    'profit': effective_sell_price - lot['cost']
                })
            else:
                unsold_lots.append(lot)
        
        self.cash += revenue
        self.lots = unsold_lots
        return sold_count

def check_trend_and_liquidity(ticker):
    """
    Checks:
    1. Trend: Price > SMA60
    2. Liquidity: Avg Daily Transaction Value > 10 Billion KRW
    """
    try:
        # Fetch 60 days for SMA, 20 days for Volume
        df = yf.download(ticker, interval="1d", period="3mo", progress=False)
        if len(df) < 60:
            return False, "Not enough data", 0, 0
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # 1. Trend Calculation
        df['SMA60'] = df['Close'].rolling(window=60).mean()
        last_row = df.iloc[-1]
        current_price = last_row['Close']
        sma60 = last_row['SMA60']
        
        if pd.isna(sma60):
            return False, "SMA60 NaN", current_price, 0
            
        is_uptrend = current_price > sma60
        
        # 2. Liquidity Calculation (Last 20 days)
        recent = df.tail(20).copy()
        recent['TxValue'] = recent['Close'] * recent['Volume']
        avg_tx_value = recent['TxValue'].mean()
        
        # 10 Billion KRW
        min_liquidity = 10_000_000_000 
        is_liquid = avg_tx_value >= min_liquidity
        
        passed = is_uptrend and is_liquid
        
        reason = []
        if not is_uptrend: reason.append(f"Price {current_price:,.0f} <= SMA {sma60:,.0f}")
        if not is_liquid: reason.append(f"Liquidity {avg_tx_value/1e8:.1f}B < 100B")
        
        msg = ", ".join(reason) if reason else "Values OK"
        
        return passed, msg, current_price, avg_tx_value
        
    except Exception as e:
        print(f"Error checking {ticker}: {e}")
        return False, str(e), 0, 0

def run_parametric_simulation(prices, dates, total_money, d_param, r_param, allocations):
    """
    allocations: List of floats summing to 1.0 (e.g. [0.4, 0.2, 0.2, 0.1, 0.1])
    """
    accounts = []
    
    # Initialize Accounts based on allocations
    for i, ratio in enumerate(allocations):
        account_idx = i + 1
        initial_cash = total_money * ratio
        name = f"Account #{account_idx}"
        acc = Account(name, initial_cash, account_idx, d_param, r_param)
        accounts.append(acc)
        
    acc1 = accounts[0] # Primary
    
    for t, price in enumerate(prices):
        current_time = dates[t]
        
        # --- Account #1 Logic ---
        acc1.check_sell_lots(price, current_time)
        
        target_acc1 = price * 1.10
        acc1.buy(price, current_time, target_price=target_acc1)
        
        # --- Account 2..M Logic ---
        ref_price = acc1.avg_price
        
        if ref_price > 0:
            for acc in accounts[1:]:
                k = acc.params['index']
                i = k - 1 # 0-based index for logic
                
                dip_factor = 1.0 - (i * d_param)
                buy_trig = ref_price * dip_factor
                
                sell_target_multiplier = 1.0 + r_param
                
                acc.check_sell_lots(price, current_time)
                
                if acc.cash > 0:
                     if price <= buy_trig:
                         lot_target = price * sell_target_multiplier
                         acc.buy(price, current_time, target_price=lot_target)

    # Final logic
    final_stats = []
    for acc in accounts:
        stock_val = acc.shares_held * prices[-1]
        final_stats.append({
            'Account': acc.name,
            'Cash': acc.cash,
            'Stock Value': stock_val,
            'Total Value': acc.cash + stock_val,
            'Trades': len(acc.trades)
        })
        
    total_val = sum(a['Total Value'] for a in final_stats)
    
    return {
        'total_profit': total_val - total_money,
        'final_stats': final_stats
    }

def run_simulation_for_stock(ticker, name, d_param, r_param, allocations):
    print(f"Processing {name} ({ticker})...", end=" ", flush=True)
    
    try:
        # Fetch last 60 days of 5m data
        df = yf.download(ticker, interval="5m", period="59d", progress=False)
        if df.empty:
            print("No data.")
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    except Exception as e:
        print(f"Error: {e}")
        return None
        
    unique_dates = sorted(list(set(df.index.date)))
    
    dataset_profits = []
    
    # Run rolling simulation (max 30 datasets)
    max_runs = 30
    for i in range(max_runs):
        if i >= len(unique_dates):
            break
        start_date = unique_dates[i]
        end_date = start_date + timedelta(days=30)
        subset = df[(df.index.date >= start_date) & (df.index.date < end_date)]
        
        if len(subset) < 100:
            continue
            
        prices = subset['Close'].values
        dates = subset.index
        
        total_money = 10_000_000
        
        res = run_parametric_simulation(
            prices, dates, 
            total_money=total_money,
            d_param=d_param, r_param=r_param,
            allocations=allocations
        )
        dataset_profits.append(res['total_profit'])
        
    if not dataset_profits:
        print("No datasets.")
        return None
        
    avg_profit = int(round(np.mean(dataset_profits)))
    win_rate = np.mean(np.array(dataset_profits) > 0) * 100
    
    print(f"Profit: {avg_profit:,}, WinRate: {win_rate:.1f}%")
    return {
        'Ticker': ticker,
        'Name': name,
        'Avg Profit': avg_profit,
        'Win Rate': win_rate
    }

def run_custom_allocation_simulation():
    # Params
    D = 0.01
    R = 0.03
    ALLOCATIONS = [0.4, 0.25, 0.15, 0.1, 0.1]
    
    print(f"Config: Custom Alloc={ALLOCATIONS}, D={D}, R={R}")
    print("Filters: 1) Price > SMA60  2) Avg Tx Value > 10 Billion KRW")
    
    # 1. Read CSV
    csv_path = "kiwoom_analysis_parameters.csv"
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    try:
        df_csv = pd.read_csv(csv_path, dtype={'Code': str}) # Ensure Code is read as string
        # Sort by Score descending
        df_csv = df_csv.sort_values(by='Score', ascending=False)
        # Select Top 50
        top_stocks = df_csv.head(50)
        
        print(f"Loaded {len(top_stocks)} stocks from Top 50 by Score.")
        
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    results = []
    
    start_time = time.time()
    
    for idx, row in top_stocks.iterrows():
        code = row['Code']
        name = row['Name']
        score = row['Score']
        
        # Add .KS suffix
        ticker = f"{code}.KS"
        
        # --- Filters ---
        passed, msg, price, liquidity = check_trend_and_liquidity(ticker)
        
        if not passed:
            print(f"Skipping {name} ({ticker}): {msg}")
            continue
            
        print(f"Pass {name}: {price:,.0f} KRW, Liquidity {liquidity/1e8:.1f}B")
        
        res = run_simulation_for_stock(ticker, name, D, R, ALLOCATIONS)
        if res:
            res['Score'] = score
            results.append(res)
            
    end_time = time.time()
    duration = end_time - start_time
    print(f"\nSimulation finished in {duration:.1f} seconds.")

    # Output
    print("\n\n=== Custom Allocation [0.4, 0.2, 0.2, 0.1, 0.1] Results ===")
    if results:
        res_df = pd.DataFrame(results)
        
        # Summary Stats
        total_avg_profit = int(round(res_df['Avg Profit'].mean()))
        avg_win_rate = res_df['Win Rate'].mean()
        
        print(f"Overall Average Profit: {total_avg_profit:,} KRW")
        print(f"Overall Average Win Rate: {avg_win_rate:.2f}%")
        print(f"Processed: {len(res_df)} / {len(top_stocks)}")
        
        print(res_df.to_string(index=False))
        res_df.to_csv("custom_allocation_results.csv", index=False)
    else:
        print("No results generated (or all filtered out).")

if __name__ == "__main__":
    run_custom_allocation_simulation()
