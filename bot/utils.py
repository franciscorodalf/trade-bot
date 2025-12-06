import yfinance as yf
import pandas as pd
import numpy as np
import ta
import json
import logging
import time
from datetime import datetime, timedelta

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

logging.basicConfig(filename=config['paths']['logs'], level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def fetch_data(symbol=None, interval=None, limit=1000):
    """
    Fetch historical data from YFinance.
    """
    symbol = symbol or config['symbol']
    interval = interval or config['timeframe']
    
    try:
        # YFinance doesn't support 'limit' directly in the same way as exchanges, 
        # so we fetch a period that covers enough data.
        period = "2y" if interval == "1d" else "60d" # Adjust based on interval
        
        df = yf.download(symbol, period=period, interval=interval, progress=False)
        
        if df.empty:
            logging.error(f"No data fetched for {symbol}")
            return None
            
        # Flatten MultiIndex columns if present (yfinance update)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })
        
        # Ensure lowercase columns
        df.columns = [c.lower() for c in df.columns]
        
        return df.tail(limit)
        
    except Exception as e:
        logging.error(f"Error fetching data: {e}")
        return None

def add_indicators(df):
    """
    Add technical indicators to the dataframe.
    """
    if df is None or df.empty:
        return None
        
    df = df.copy()
    
    # Returns
    df['return'] = df['close'].pct_change()
    
    # Simple Moving Averages
    df['sma_20'] = ta.trend.sma_indicator(df['close'], window=20)
    df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50)
    
    # Exponential Moving Average
    df['ema_12'] = ta.trend.ema_indicator(df['close'], window=12)
    
    # RSI
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    
    # Volatility (Bollinger Bands Width or standard deviation of returns)
    df['volatility'] = df['return'].rolling(window=20).std()
    
    # Lag features (previous values to predict next)
    for lag in [1, 2, 3]:
        df[f'return_lag_{lag}'] = df['return'].shift(lag)
        df[f'rsi_lag_{lag}'] = df['rsi'].shift(lag)
        df[f'volatility_lag_{lag}'] = df['volatility'].shift(lag)
        
    # Target: 1 if next close > current close, else 0
    df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
    
    # Drop NaNs created by indicators and shifting
    df = df.dropna()
    
    return df

def get_latest_data_with_indicators():
    """
    Fetch latest data and add indicators for real-time prediction.
    """
    df = fetch_data(limit=100) # Fetch enough for indicators
    if df is not None:
        df = add_indicators(df)
        return df
    return None
