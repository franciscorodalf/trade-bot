"""Tests for the features module."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))

import numpy as np
from features import FEATURE_COLUMNS, _compute_rsi, _ema


class TestFeatureColumns:
    def test_feature_count(self):
        """Should have 40 features."""
        assert len(FEATURE_COLUMNS) == 40

    def test_no_duplicates(self):
        """No duplicate feature names."""
        assert len(FEATURE_COLUMNS) == len(set(FEATURE_COLUMNS))

    def test_categories_present(self):
        """All feature categories should be represented."""
        names = " ".join(FEATURE_COLUMNS)
        assert "return" in names
        assert "rsi" in names
        assert "macd" in names
        assert "bb" in names
        assert "atr" in names
        assert "spread" in names
        assert "book_imbalance" in names
        assert "cvd" in names
        assert "volume" in names
        assert "funding" in names
        assert "fear_greed" in names


class TestRSI:
    def test_rsi_neutral(self):
        """RSI should be ~50 for sideways market."""
        closes = np.array([100 + (i % 2) for i in range(20)])
        rsi = _compute_rsi(closes, 14)
        assert 40 < rsi < 60

    def test_rsi_overbought(self):
        """RSI should be high for consistently rising prices."""
        closes = np.array([100 + i for i in range(20)])
        rsi = _compute_rsi(closes, 14)
        assert rsi > 80

    def test_rsi_oversold(self):
        """RSI should be low for consistently falling prices."""
        closes = np.array([100 - i for i in range(20)])
        rsi = _compute_rsi(closes, 14)
        assert rsi < 20

    def test_rsi_insufficient_data(self):
        """Should return 50 when insufficient data."""
        rsi = _compute_rsi(np.array([100, 101]), 14)
        assert rsi == 50.0


class TestEMA:
    def test_ema_follows_trend(self):
        """EMA should be close to recent values in a trend."""
        data = np.array([100 + i for i in range(30)])
        ema_val = _ema(data, 12)
        assert ema_val > 120

    def test_ema_single_value(self):
        """EMA of single value should be that value."""
        ema_val = _ema(np.array([42.0]), 12)
        assert ema_val == 42.0
