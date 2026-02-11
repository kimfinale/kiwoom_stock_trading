import numpy as np
from scipy.optimize import minimize
from simulate_algorithm import simulate_strategy
import data_loader as dl

def optimize_params():
    # 1. Fetch Real Data
    TICKER = "005930" # Samsung Electronics
    print(f"Fetching 1-year data for {TICKER} (Interval: 1h)...")
    # yfinance limit for 1h is 730 days, so 1y is fine.
    # Note: 10m/5m data is limited to 60 days, so we use 1h for 1 year analysis.
    df = dl.get_price_data(TICKER, interval="1h", period="1y")
    
    if df.empty:
        print("Error: Could not fetch data via yfinance. Trying Daily as fallback...")
        df = dl.get_price_data(TICKER, interval="daily", period="1y")
        
    if df.empty:
        print("Error: Could not fetch data.")
        return
        
    prices = df['Close'].values
    print(f"Loaded {len(prices)} data points from real data.")
    
    # Wrap in list for simulate_strategy (now multi-stock capable)
    price_series_list = [prices]

    # 2. Define Objective Function
    def objective(params, n_accounts, price_series_list):
        """
        Objective function to minimize.
        params: [R, S, PRIMARY_RATIO]
        """
        r, s, primary_ratio = params
        
        # Constraints/Penalties
        if r <= 0.001 or s <= 0.001 or primary_ratio <= 0.1 or primary_ratio >= 0.9:
            return 1e6 
            
        sim_params = {
            'TOTAL_MONEY': 1_000_000,
            'R': r,
            'S': s,
            'PRIMARY_RATIO': primary_ratio,
            'TOTAL_ACCOUNTS': int(n_accounts),
            # Optimize assumes uniform predictors or we just let default logic handle
            # The current simulation uses ALLOCATION_DIVISORS. 
            # We should stick to a default pattern or optimize them too?
            # Let's keep them fixed to [3, 3, 3, 3...] for now or generate based on N
            'ALLOCATION_DIVISORS': [3.0] * int(n_accounts) 
        }
        
        result = simulate_strategy(price_series_list, sim_params)
        return -result['return_pct'] 

    # Grid Search for Robustness (Simulation is non-smooth)
    best_overall_return = -np.inf
    best_overall_config = None

    # Define ranges
    r_list = [0.01, 0.03, 0.05]
    s_list = [0.02, 0.05, 0.10]
    ratio_list = [0.4, 0.6]
    accounts_list = [2, 3, 5, 7]
    
    # Iterate
    for n_acc in accounts_list:
        for r_val in r_list:
            for s_val in s_list:
                for ratio in ratio_list:
                    # Run simulation
                    current_return = -objective([r_val, s_val, ratio], n_acc, price_series_list)
                    
                    # Log result (maybe skip printing all to avoid clutter, just best)
                    # print(f"Acc:{n_acc} R:{r_val} S:{s_val} Ratio:{ratio} -> {current_return:.2f}%")
                    
                    if current_return > best_overall_return:
                        best_overall_return = current_return
                        best_overall_config = {
                            'n_accounts': n_acc,
                            'return': current_return,
                            'R': r_val,
                            'S': s_val,
                            'primary_ratio': ratio
                        }
                        print(f"New Best: {best_overall_return:.2f}% (Acc:{n_acc}, R:{r_val}, S:{s_val}, Ratio:{ratio})")

    print("-" * 60)
    
    # Save results
    with open("optimization_results.txt", "w") as f:
        f.write("Optimization Results (Samsung 1-Year 1h Data - Grid Search):\n")
        f.write("*** Best Configuration Found ***\n")
        if best_overall_config:
            f.write(f"Total Accounts: {best_overall_config['n_accounts']}\n")
            f.write(f"Return: {best_overall_config['return']:.2f}%\n")
            f.write(f"R: {best_overall_config['R']:.4f}\n")
            f.write(f"S: {best_overall_config['S']:.4f}\n")
            f.write(f"Primary Account Ratio: {best_overall_config['primary_ratio']:.4f}\n")

    if best_overall_config:
        print("\n*** Best Configuration Found ***")
        print(f"Total Accounts: {best_overall_config['n_accounts']}")
        print(f"Return: {best_overall_config['return']:.2f}%")
        print(f"R: {best_overall_config['R']:.4f}")
        print(f"S: {best_overall_config['S']:.4f}")
        print(f"Primary Account Ratio: {best_overall_config['primary_ratio']:.4f}")

if __name__ == "__main__":
    optimize_params()
