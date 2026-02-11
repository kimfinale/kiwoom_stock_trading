
import pandas as pd
import FinanceDataReader as fdr
import yfinance as yf
from datetime import datetime, timedelta

def check_fdr_intraday():
    print("--- Checking FinanceDataReader (KRX) ---")
    # Ticker for Samsung Electronics
    ticker = "005930" 
    
    # Try fetching daily data first to confirm it works
    try:
        df_daily = fdr.DataReader(ticker, "2023-01-01", "2023-01-10")
        print(f"Daily Data (Head):\n{df_daily.head()}")
    except Exception as e:
        print(f"Daily Data Error: {e}")

    # FDR usually doesn't support intraday for KRX via public sources easily, but let's check if there's any undocumented way or if I am mistaken.
    # Actually, recent versions might support it via 'Naver' or similar, but typically it returns daily. 
    # Let's try to get a shorter range and see if it infers intraday? (Unlikely)
    
def check_yfinance_intraday():
    print("\n--- Checking yfinance (KRX) ---")
    # Ticker for Samsung Electronics on Yahoo Finance
    ticker = "005930.KS"
    
    try:
        # Fetch 5-minute data for the last 5 days (yfinance limit for 5m is usually 60 days)
        # 1m data is limited to 7 days.
        data = yf.download(ticker, period="5d", interval="5m", progress=False)
        if not data.empty:
            print(f"5-minute Data (Last 5 days):\n{data.head()}")
            print(f"Total Rows: {len(data)}")
        else:
            print("No 5-minute data found for 005930.KS")
            
        # Check max history for 1h data (730 days usually)
        print("\n--- Checking 1h data (longer history) ---")
        data_1h = yf.download(ticker, period="1y", interval="1h", progress=False)
        if not data_1h.empty:
            print(f"1-hour Data (Last 1 year):\n{data_1h.head()}")
            print(f"Total Rows: {len(data_1h)}")
        else:
            print("No 1-hour data found.")

    except Exception as e:
        print(f"yfinance Error: {e}")

if __name__ == "__main__":
    check_fdr_intraday()
    check_yfinance_intraday()
