import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def get_stock_list(market="KOSPI"):
    """
    Fetches the list of stocks for the specified market.
    Defaults to KOSPI.
    """
    try:
        df = fdr.StockListing(market)
        return df
    except Exception as e:
        print(f"Error fetching stock list: {e}")
        return pd.DataFrame()

def get_price_data(ticker, interval="daily", period="1y"):
    """
    Fetches price data for a given ticker.
    
    Args:
        ticker (str): The stock ticker (e.g., '005930').
        interval (str): 'daily' or 'minute' (or specific like '5m').
        period (str): Duration (e.g., '1y', '5d').
        
    Returns:
        pd.DataFrame: DataFrame with columns ['Open', 'High', 'Low', 'Close', 'Volume']
    """
    # 1. Try yfinance for intraday/minute/hourly data
    if "m" in interval or "h" in interval:
        start_date = None
        end_date = datetime.now()
        
        # Adjust period for yfinance
        # yfinance period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        yf_ticker = f"{ticker}.KS" # Append .KS for KOSPI
        
        try:
            print(f"Fetching {interval} data for {yf_ticker} via yfinance...")
            # Note: yfinance max period for 1m is 7d, 5m is 60d
            df = yf.download(yf_ticker, period=period, interval=interval, progress=False)
            
            if not df.empty:
               # Clean up MultiIndex columns if present (yfinance update)
               if isinstance(df.columns, pd.MultiIndex):
                   df.columns = df.columns.get_level_values(0)
               
               df = df.rename(columns={
                   "Open": "Open", "High": "High", "Low": "Low", 
                   "Close": "Close", "Volume": "Volume"
               })
               # Ensure datetime index
               df.index = pd.to_datetime(df.index)
               return df[['Open', 'High', 'Low', 'Close', 'Volume']]
            else:
                print(f"yfinance returned empty data for {yf_ticker}")

        except Exception as e:
            print(f"yfinance failed: {e}")

    # 2. Fallback to FinanceDataReader (Daily data)
    # FDR is reliable for daily KRX data
    if interval == "daily" or True: # Fallback for any interval if yfinance failed
        print(f"Fetching daily data for {ticker} via FinanceDataReader...")
        try:
            # Parse period to start date
            end_date = datetime.now()
            if period == "1y":
                start_date = end_date - timedelta(days=365)
            elif period == "5d":
                start_date = end_date - timedelta(days=7) # generous buffer
            else:
                # Default
                start_date = end_date - timedelta(days=365)
            
            df = fdr.DataReader(ticker, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            
            if not df.empty:
                df = df.rename(columns={
                    "Open": "Open", "High": "High", "Low": "Low", 
                    "Close": "Close", "Volume": "Volume"
                })
                return df[['Open', 'High', 'Low', 'Close', 'Volume']]
        except Exception as e:
            print(f"FinanceDataReader failed: {e}")
            
    return pd.DataFrame()

if __name__ == "__main__":
    # Test
    print("Testing get_stock_list...")
    stocks = get_stock_list()
    print(f"Fetched {len(stocks)} stocks.")
    
    ticker = "005930"
    print(f"\nTesting get_price_data for {ticker} (Daily)...")
    df_daily = get_price_data(ticker, interval="daily", period="5d")
    print(df_daily.head())
    
    print(f"\nTesting get_price_data for {ticker} (5m)...")
    df_minute = get_price_data(ticker, interval="5m", period="5d")
    print(df_minute.head())
