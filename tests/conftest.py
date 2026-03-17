"""
Shared fixtures for the AI Trading Bot test suite.
Provides mock configurations, sample market data, and database setup.
"""

import pytest
import json
import os
import sys
import sqlite3
import tempfile
import shutil
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ---- Path Setup ----
# Ensure project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'bot'))


# ---- Test Configuration ----
TEST_CONFIG = {
    "initial_capital": 100.0,
    "binance": {
        "api_key": "",
        "api_secret": "",
        "testnet": False
    },
    "risk_per_trade": 0.02,
    "buy_threshold": 0.55,
    "sell_threshold": 0.40,
    "commission_rate": 0.0005,
    "slippage": 0.0003,
    "volatility_threshold": 0.002,
    "symbols": ["BTC/USDT", "ETH/USDT"],
    "max_open_positions": 3,
    "timeframe": "1h",
    "model_params": {
        "n_estimators": 10,
        "max_depth": 5,
        "min_samples_leaf": 5,
        "random_state": 42
    },
    "paths": {
        "model": "",
        "database": "",
        "logs": ""
    }
}


@pytest.fixture
def config():
    """Return a copy of the test configuration."""
    return TEST_CONFIG.copy()


@pytest.fixture
def tmp_dir(tmp_path):
    """Create a temporary directory structure mimicking the project."""
    db_dir = tmp_path / "database"
    log_dir = tmp_path / "logs"
    model_dir = tmp_path / "bot" / "models"
    db_dir.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    model_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def config_with_paths(tmp_dir):
    """Config with valid temporary paths."""
    cfg = TEST_CONFIG.copy()
    cfg["paths"] = {
        "model": str(tmp_dir / "bot" / "models" / "model.pkl"),
        "database": str(tmp_dir / "database" / "bot.db"),
        "logs": str(tmp_dir / "logs" / "bot.log"),
    }
    return cfg


@pytest.fixture
def config_file(tmp_dir, config_with_paths):
    """Write config.json to temp directory and return its path."""
    config_path = tmp_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(config_with_paths, f)
    return str(config_path)


@pytest.fixture
def sample_ohlcv_df():
    """
    Generate a realistic OHLCV DataFrame for testing.
    200 rows of synthetic hourly candle data.
    """
    np.random.seed(42)
    n = 200
    base_price = 50000.0  # BTC-like

    dates = pd.date_range(start="2026-01-01", periods=n, freq="1h")

    # Random walk for close prices
    returns = np.random.normal(0.0002, 0.01, n)
    close = base_price * np.cumprod(1 + returns)

    # Generate OHLC from close
    high = close * (1 + np.abs(np.random.normal(0, 0.005, n)))
    low = close * (1 - np.abs(np.random.normal(0, 0.005, n)))
    open_price = close * (1 + np.random.normal(0, 0.003, n))
    volume = np.random.uniform(100, 5000, n)

    df = pd.DataFrame({
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    }, index=dates)

    df.index.name = "timestamp"
    return df


@pytest.fixture
def small_ohlcv_df():
    """Small OHLCV DataFrame (10 rows) for edge case testing."""
    np.random.seed(99)
    n = 10
    dates = pd.date_range(start="2026-03-01", periods=n, freq="1h")
    close = np.linspace(100, 110, n)

    return pd.DataFrame({
        "open": close * 0.999,
        "high": close * 1.005,
        "low": close * 0.995,
        "close": close,
        "volume": np.random.uniform(50, 200, n)
    }, index=dates)


@pytest.fixture
def test_db(tmp_dir, config_with_paths):
    """Create a test SQLite database with schema and sample data."""
    db_path = config_with_paths["paths"]["database"]
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Create schema
    c.execute('''CREATE TABLE IF NOT EXISTS balance_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  balance REAL, equity REAL,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('''CREATE TABLE IF NOT EXISTS trades
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  symbol TEXT, side TEXT, price REAL, amount REAL,
                  cost REAL, fee REAL, pnl REAL, status TEXT, reason TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('''CREATE TABLE IF NOT EXISTS signals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  symbol TEXT, signal_type TEXT, probability REAL,
                  close_price REAL,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    # Insert sample data
    c.execute("INSERT INTO balance_history (balance, equity) VALUES (100.0, 105.0)")

    c.execute("""INSERT INTO trades (symbol, side, price, amount, cost, fee, pnl, status, reason)
                 VALUES ('BTC/USDT', 'BUY', 50000.0, 0.002, 100.0, 0.05, 0, 'OPEN', 'SIGNAL')""")
    c.execute("""INSERT INTO trades (symbol, side, price, amount, cost, fee, pnl, status, reason)
                 VALUES ('BTC/USDT', 'SELL', 51000.0, 0.002, 102.0, 0.051, 2.0, 'CLOSED', 'TP')""")
    c.execute("""INSERT INTO trades (symbol, side, price, amount, cost, fee, pnl, status, reason)
                 VALUES ('ETH/USDT', 'BUY', 3000.0, 0.033, 99.0, 0.05, 0, 'OPEN', 'SIGNAL')""")
    c.execute("""INSERT INTO trades (symbol, side, price, amount, cost, fee, pnl, status, reason)
                 VALUES ('ETH/USDT', 'SELL', 2950.0, 0.033, 97.35, 0.049, -1.65, 'CLOSED', 'SL')""")

    c.execute("""INSERT INTO signals (symbol, signal_type, probability, close_price)
                 VALUES ('BTC/USDT', 'BUY', 0.72, 50000.0)""")
    c.execute("""INSERT INTO signals (symbol, signal_type, probability, close_price)
                 VALUES ('ETH/USDT', 'SELL', 0.35, 3000.0)""")
    c.execute("""INSERT INTO signals (symbol, signal_type, probability, close_price)
                 VALUES ('BTC/USDT', 'HOLD', 0.50, 50500.0)""")

    conn.commit()
    conn.close()
    return db_path
