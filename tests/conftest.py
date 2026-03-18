"""
Shared test fixtures for the Polymarket BTC Prediction Bot.
"""

import pytest
import numpy as np


@pytest.fixture
def sample_features():
    """Sample feature dict matching FEATURE_COLUMNS."""
    return {
        "return_1m": 0.001, "return_5m": 0.003, "return_15m": -0.002, "return_30m": 0.005,
        "log_return_1m": 0.001, "log_return_5m": 0.003,
        "volatility_5m": 0.002, "volatility_15m": 0.003,
        "rsi_14": 55.0, "rsi_7": 60.0,
        "macd": 5.0, "macd_signal": 3.0, "macd_hist": 2.0,
        "price_vs_sma_20": 50.0,
        "bb_position": 0.6, "bb_width": 200.0,
        "atr_14": 150.0, "atr_ratio": 20.0,
        "spread_bps": 1.5, "spread_change": 0.0,
        "book_imbalance_5": 0.15, "book_imbalance_10": 0.10, "book_imbalance_20": 0.05,
        "bid_depth_usd": 5000000, "ask_depth_usd": 4500000, "depth_ratio": 1.11,
        "buy_sell_ratio_1m": 1.2, "buy_sell_ratio_5m": 1.1,
        "cvd_1m": 0.05, "cvd_5m": 0.08,
        "trade_intensity_1m": 15.0, "trade_intensity_5m": 12.0,
        "large_trade_ratio": 0.15,
        "volume_ratio_5m": 1.3, "volume_ratio_15m": 1.1,
        "volume_momentum": 0.2,
        "funding_rate": 0.0001, "funding_rate_abs": 0.0001,
        "open_interest_change": 0.0,
        "fear_greed_normalized": 0.3,
    }
