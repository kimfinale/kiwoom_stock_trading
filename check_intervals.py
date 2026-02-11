
import yfinance as yf
from datetime import datetime, timedelta

def check_intervals():
    tickers = ["005930.KS", "000660.KS"] # Samsung Elec, SK Hynix
    intervals = ["15m", "30m", "60m"]
    
    print(f"Checking intervals: {intervals} for past 70 days...")
    
    for ticker in tickers:
        print(f"\n--- Ticker: {ticker} ---")
        for interval in intervals:
            try:
                # Try to get > 60 days of data
                # yfinance limitation: 
                # 1m, 2m, 5m, 15m, 30m often limited to 60 days
                # 60m, 90m, 1h limited to 730 days
                
                # Let's try fetching 70 days to see if 30m works
                data = yf.download(ticker, period="70d", interval=interval, progress=False)
                if not data.empty:
                    print(f"[{interval}] Success for 70d! Rows: {len(data)}")
                    print(f"Start: {data.index[0]}, End: {data.index[-1]}")
                else:
                    print(f"[{interval}] Failed/Empty for 70d.")
                    
                # Try 1y for larger intervals
                if interval in ["60m", "1h"]:
                    data_1y = yf.download(ticker, period="1y", interval=interval, progress=False)
                    if not data_1y.empty:
                         print(f"[{interval}] Success for 1y! Rows: {len(data_1y)}")
            except Exception as e:
                print(f"[{interval}] Error: {e}")

if __name__ == "__main__":
    check_intervals()
