import ccxt
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
    Fetch historical data from Binance using CCXT.
    """
    symbol = symbol or config.get('symbol') or config.get('symbols', [])[0]
    interval = interval or config['timeframe']
    
    retries = 3
    for attempt in range(retries):
        try:
            # Use public API for now (no keys required for fetching data)
            exchange = ccxt.binance({
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future' # Use futures data by default as requested/implied by "robust"
                }
            })
            
            # Check if keys are provided in config for higher limits (optional)
            if config.get('binance', {}).get('api_key'):
                 exchange.apiKey = config['binance']['api_key']
                 exchange.secret = config['binance']['api_secret']

            # Fetch OHLCV
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=interval, limit=limit)
            
            if not ohlcv:
                logging.warning(f"Attempt {attempt+1}: No data fetched for {symbol}. Retrying...")
                time.sleep(2)
                continue
                
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            logging.warning(f"Attempt {attempt+1} failed for {symbol}: {e}. Retrying in 2s...")
            time.sleep(2)
            
    logging.error(f"Failed to fetch data for {symbol} after {retries} attempts.")
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
    
    # MACD
    df['macd'] = ta.trend.macd_diff(df['close'])

    # Bollinger Bands Width
    df['bb_width'] = ta.volatility.bollinger_wband(df['close'], window=20, window_dev=2)
    
    # ATR (Average True Range) for Risk Management
    df['atr'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range()
    
    # Lag features (previous values to predict next)
    for lag in [1, 2, 3]:
        df[f'return_lag_{lag}'] = df['return'].shift(lag)
        df[f'rsi_lag_{lag}'] = df['rsi'].shift(lag)
        df[f'volatility_lag_{lag}'] = df['volatility'].shift(lag)
        df[f'macd_lag_{lag}'] = df['macd'].shift(lag)
        df[f'bb_width_lag_{lag}'] = df['bb_width'].shift(lag)
        
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
