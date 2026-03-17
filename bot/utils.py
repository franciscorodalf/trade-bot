"""
Data fetching and technical indicator calculation utilities.

This module provides the data pipeline: fetching OHLCV candles from Binance
via CCXT and computing 25 technical features used by the ML model.
"""

import ccxt
import pandas as pd
import numpy as np
import ta
import json
import logging
import time
from typing import Optional, List

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

logging.basicConfig(
    filename=config['paths']['logs'],
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Feature columns used by the ML model (shared constant)
FEATURE_COLUMNS: List[str] = [
    'return', 'sma_20', 'sma_50', 'ema_12', 'rsi', 'volatility', 'atr',
    'macd', 'bb_width',
    'return_lag_1', 'return_lag_2', 'return_lag_3',
    'rsi_lag_1', 'rsi_lag_2', 'rsi_lag_3',
    'volatility_lag_1', 'volatility_lag_2', 'volatility_lag_3',
    'macd_lag_1', 'macd_lag_2', 'macd_lag_3',
    'bb_width_lag_1', 'bb_width_lag_2', 'bb_width_lag_3'
]


def fetch_data(
    symbol: Optional[str] = None,
    interval: Optional[str] = None,
    limit: int = 1000
) -> Optional[pd.DataFrame]:
    """
    Fetch historical OHLCV data from Binance Futures using CCXT.

    Args:
        symbol: Trading pair (e.g. 'BTC/USDT'). Defaults to first configured symbol.
        interval: Candlestick timeframe (e.g. '1h'). Defaults to config timeframe.
        limit: Number of candles to fetch (max ~1500 per request).

    Returns:
        DataFrame with columns [open, high, low, close, volume] indexed by timestamp,
        or None if all retry attempts fail.
    """
    symbol = symbol or config.get('symbol') or config.get('symbols', [])[0]
    interval = interval or config['timeframe']

    retries = 3
    for attempt in range(retries):
        try:
            exchange = ccxt.binance({
                'enableRateLimit': True,
                'options': {'defaultType': 'future'}
            })

            # Attach API keys if available (optional, for higher rate limits)
            if config.get('binance', {}).get('api_key'):
                exchange.apiKey = config['binance']['api_key']
                exchange.secret = config['binance']['api_secret']

            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=interval, limit=limit)

            if not ohlcv:
                logging.warning(f"Attempt {attempt + 1}: No data for {symbol}. Retrying...")
                time.sleep(2)
                continue

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            return df

        except ccxt.NetworkError as e:
            logging.warning(f"Network error fetching {symbol} (attempt {attempt + 1}): {e}")
            time.sleep(3)
        except ccxt.ExchangeError as e:
            logging.error(f"Exchange error for {symbol}: {e}")
            return None
        except Exception as e:
            logging.warning(f"Attempt {attempt + 1} failed for {symbol}: {e}. Retrying...")
            time.sleep(2)

    logging.error(f"Failed to fetch data for {symbol} after {retries} attempts.")
    return None


def add_indicators(df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """
    Calculate technical indicators and generate ML features.

    Computes 25 features across 4 categories:
    - Trend: SMA(20), SMA(50), EMA(12), MACD
    - Momentum: RSI(14)
    - Volatility: Bollinger Band Width, ATR(14), return std deviation
    - Lag features: t-1, t-2, t-3 for return, RSI, volatility, MACD, BB width

    Also generates the binary target variable (1 if next candle is up, 0 otherwise).

    Args:
        df: OHLCV DataFrame with at least 50+ rows for accurate indicators.

    Returns:
        DataFrame with all features added and NaN rows dropped,
        or None if input is invalid.
    """
    if df is None or df.empty:
        return None

    df = df.copy()

    # Price returns
    df['return'] = df['close'].pct_change()

    # Trend indicators
    df['sma_20'] = ta.trend.sma_indicator(df['close'], window=20)
    df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50)
    df['ema_12'] = ta.trend.ema_indicator(df['close'], window=12)
    df['macd'] = ta.trend.macd_diff(df['close'])

    # Momentum
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)

    # Volatility
    df['volatility'] = df['return'].rolling(window=20).std()
    df['bb_width'] = ta.volatility.bollinger_wband(df['close'], window=20, window_dev=2)
    df['atr'] = ta.volatility.AverageTrueRange(
        df['high'], df['low'], df['close'], window=14
    ).average_true_range()

    # Lag features (temporal context for the model)
    for lag in [1, 2, 3]:
        df[f'return_lag_{lag}'] = df['return'].shift(lag)
        df[f'rsi_lag_{lag}'] = df['rsi'].shift(lag)
        df[f'volatility_lag_{lag}'] = df['volatility'].shift(lag)
        df[f'macd_lag_{lag}'] = df['macd'].shift(lag)
        df[f'bb_width_lag_{lag}'] = df['bb_width'].shift(lag)

    # Target: binary classification (next candle up = 1, down = 0)
    df['target'] = (df['close'].shift(-1) > df['close']).astype(int)

    # Drop rows with NaN from indicator warm-up period
    df = df.dropna()

    return df


def get_latest_data_with_indicators(
    symbol: Optional[str] = None,
    limit: int = 100
) -> Optional[pd.DataFrame]:
    """
    Convenience function: fetch recent candles and compute all indicators.

    Args:
        symbol: Trading pair. Defaults to config.
        limit: Number of candles to fetch (100 recommended for indicator accuracy).

    Returns:
        DataFrame with OHLCV + all indicators, or None on failure.
    """
    df = fetch_data(symbol=symbol, limit=limit)
    if df is not None:
        return add_indicators(df)
    return None
