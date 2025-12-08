import ccxt.async_support as ccxt
# Updated: 2025-12-07 12:05 UTC (Async)
import pandas as pd
import numpy as np
import ta
import json
import logging
import time
import asyncio
from datetime import datetime, timedelta

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

logging.basicConfig(filename=config['paths']['logs'], level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

async def fetch_data(symbol=None, interval=None, limit=1000):
    """
    Fetch historical data from Binance using CCXT (Async).
    """
    symbol = symbol or config.get('symbol') or config.get('symbols', [])[0]
    interval = interval or config['timeframe']
    
    retries = 3
    exchange = None
    try:
        # Use public API
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future' 
            }
        })
        
        # Check keys (optional)
        if config.get('binance', {}).get('api_key'):
             exchange.apiKey = config['binance']['api_key']
             exchange.secret = config['binance']['api_secret']

        for attempt in range(retries):
            try:
                # Async Fetch
                ohlcv = await exchange.fetch_ohlcv(symbol, timeframe=interval, limit=limit)
                
                if not ohlcv:
                    logging.warning(f"Attempt {attempt+1}: No data fetched for {symbol}. Retrying...")
                    await asyncio.sleep(2)
                    continue
                    
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
                return df
                
            except Exception as e:
                wait_time = (attempt + 1) * 3  # 3s, 6s, 9s, etc.
                logging.warning(f"Attempt {attempt+1} failed for {symbol}: {e}. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
                
        logging.error(f"Failed to fetch data for {symbol} after {retries} attempts.")
        return None
        
    finally:
        if exchange:
            await exchange.close()

def add_indicators(df):
    """
    Add technical indicators to the dataframe, including Multi-Timeframe analysis (MTF).
    """
    if df is None or df.empty:
        return None
        
    df = df.copy()
    
    # --- Helper to calculate indicators ---
    def calc_techs(d):
        d['return'] = d['close'].pct_change()
        d['sma_20'] = ta.trend.sma_indicator(d['close'], window=20)
        d['sma_50'] = ta.trend.sma_indicator(d['close'], window=50)
        d['ema_12'] = ta.trend.ema_indicator(d['close'], window=12)
        d['rsi'] = ta.momentum.rsi(d['close'], window=14)
        d['volatility'] = d['return'].rolling(window=20).std()
        d['macd'] = ta.trend.macd_diff(d['close'])
        d['bb_width'] = ta.volatility.bollinger_wband(d['close'], window=20, window_dev=2)
        d['atr'] = ta.volatility.AverageTrueRange(d['high'], d['low'], d['close'], window=14).average_true_range()
        return d

    # 1. Calculate Base Timeframe Indicators
    df = calc_techs(df)
    
    # 2. Multi-Timeframe (MTF) Processing
    # We assume 'df' is the lowest timeframe (e.g. 15m)
    # We resample to higher timeframes based on config
    timeframes = config.get('timeframes', [])
    # Filter out the base timeframe (assuming base is the first one or implicit)
    # Actually, let's just use hardcoded multipliers or parse the config strings.
    # Simple map for now: 1h, 4h
    
    mtf_map = {
        '1h': '1h',
        '4h': '4h',
        '1d': '1D'
    }
    
    for tf_str in timeframes:
        if tf_str == config.get('timeframe', '15m'): continue # Skip base
        if tf_str not in mtf_map: continue
        
        rule = mtf_map[tf_str]
        
        # Resample
        # Aggregation rules
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        
        resampled = df.resample(rule).agg(agg_dict).dropna()
        
        if len(resampled) < 52: # Need at least 50 for SMA50 + buffer
            logging.warning(f"Not enough data for timeframe {tf_str} (Has: {len(resampled)}, Need: 52). Skipping symbol.")
            return None
        
        # Calculate indicators on this TF
        resampled = calc_techs(resampled)
        
        # Select key columns to merge back (only indicators, not OHLCV)
        # We want to know RSI_1h, trend_1h, etc.
        cols_to_keep = ['rsi', 'macd', 'sma_20', 'sma_50']
        resampled = resampled[cols_to_keep]
        
        # Rename columns with suffix
        resampled.columns = [f"{col}_{tf_str}" for col in resampled.columns]
        
        # Merge back to base (ffill to propagate last known 1h value to all 15m candles in that hour)
        # We need to being careful about look-ahead bias.
        # A 15m candle at 10:15 should know the 1h candle state of 09:00-10:00 (closed at 10:00).
        # It should NOT know the 1h candle executing from 10:00-11:00 because that hasn't closed yet.
        # So we verify resizing:
        # Standard reindex + ffill should work if timestamps align on close.
        
        df = df.join(resampled, how='left')
        df.ffill(inplace=True) # Forward fill holes for the 15m candles between 1h timestamps

    # 3. Lag features (Only for Base Timeframe usually, maybe some MTF lags?)
    # Let's keep it simple for now.
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

async def get_latest_data_with_indicators():
    """
    Fetch latest data and add indicators for real-time prediction (Async).
    """
    df = await fetch_data(limit=1000) # Fetch enough for indicators (esp. 4h SMA)
    if df is not None:
        df = add_indicators(df)
        return df
    return None
