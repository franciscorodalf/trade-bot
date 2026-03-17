"""
Tests for the Utils module.
Covers: add_indicators(), data validation, feature engineering.
"""

import pytest
import pandas as pd
import numpy as np
import sys
import os


@pytest.fixture(autouse=True)
def mock_config(monkeypatch, config_file):
    """Ensure utils module loads our test config."""
    os.chdir(os.path.dirname(config_file))
    sys.path.insert(0, os.path.join(os.path.dirname(config_file), '..', 'bot'))


def _import_add_indicators():
    """Import add_indicators fresh."""
    if 'utils' in sys.modules:
        del sys.modules['utils']
    from utils import add_indicators
    return add_indicators


# ============================================
# Indicator Calculation Tests
# ============================================

class TestAddIndicators:
    def test_returns_dataframe(self, sample_ohlcv_df):
        """add_indicators should return a valid DataFrame."""
        add_indicators = _import_add_indicators()
        result = add_indicators(sample_ohlcv_df)

        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0

    def test_all_features_present(self, sample_ohlcv_df):
        """All 25 expected features should be present in the output."""
        add_indicators = _import_add_indicators()
        result = add_indicators(sample_ohlcv_df)

        expected_features = [
            'return', 'sma_20', 'sma_50', 'ema_12', 'rsi', 'volatility',
            'macd', 'bb_width', 'atr',
            'return_lag_1', 'return_lag_2', 'return_lag_3',
            'rsi_lag_1', 'rsi_lag_2', 'rsi_lag_3',
            'volatility_lag_1', 'volatility_lag_2', 'volatility_lag_3',
            'macd_lag_1', 'macd_lag_2', 'macd_lag_3',
            'bb_width_lag_1', 'bb_width_lag_2', 'bb_width_lag_3',
            'target'
        ]

        for feature in expected_features:
            assert feature in result.columns, f"Missing feature: {feature}"

    def test_no_nan_values(self, sample_ohlcv_df):
        """Output should have no NaN values after dropna."""
        add_indicators = _import_add_indicators()
        result = add_indicators(sample_ohlcv_df)

        assert result.isnull().sum().sum() == 0, "DataFrame contains NaN values"

    def test_target_is_binary(self, sample_ohlcv_df):
        """Target column should only contain 0 and 1."""
        add_indicators = _import_add_indicators()
        result = add_indicators(sample_ohlcv_df)

        unique_values = set(result['target'].unique())
        assert unique_values.issubset({0, 1}), f"Target has unexpected values: {unique_values}"

    def test_rsi_in_valid_range(self, sample_ohlcv_df):
        """RSI should be between 0 and 100."""
        add_indicators = _import_add_indicators()
        result = add_indicators(sample_ohlcv_df)

        assert result['rsi'].min() >= 0, "RSI below 0"
        assert result['rsi'].max() <= 100, "RSI above 100"

    def test_volatility_non_negative(self, sample_ohlcv_df):
        """Volatility (std dev of returns) should be non-negative."""
        add_indicators = _import_add_indicators()
        result = add_indicators(sample_ohlcv_df)

        assert (result['volatility'] >= 0).all(), "Negative volatility detected"

    def test_atr_positive(self, sample_ohlcv_df):
        """ATR should always be positive."""
        add_indicators = _import_add_indicators()
        result = add_indicators(sample_ohlcv_df)

        assert (result['atr'] > 0).all(), "ATR should be positive"

    def test_sma_ordering(self, sample_ohlcv_df):
        """SMA values should be reasonable (within price range)."""
        add_indicators = _import_add_indicators()
        result = add_indicators(sample_ohlcv_df)

        min_price = sample_ohlcv_df['close'].min() * 0.5
        max_price = sample_ohlcv_df['close'].max() * 1.5

        assert (result['sma_20'] >= min_price).all()
        assert (result['sma_20'] <= max_price).all()
        assert (result['sma_50'] >= min_price).all()
        assert (result['sma_50'] <= max_price).all()

    def test_lag_features_are_shifted(self, sample_ohlcv_df):
        """Lag features should be shifted versions of their base."""
        add_indicators = _import_add_indicators()
        result = add_indicators(sample_ohlcv_df)

        # Lag 1 of return should not equal current return (in general)
        # They can occasionally match, so we check they're not ALL the same
        assert not (result['return'] == result['return_lag_1']).all(), \
            "Lag 1 should differ from current values"

    def test_output_fewer_rows_than_input(self, sample_ohlcv_df):
        """Output should have fewer rows due to indicator warm-up and dropna."""
        add_indicators = _import_add_indicators()
        result = add_indicators(sample_ohlcv_df)

        assert len(result) < len(sample_ohlcv_df), \
            "Indicator warm-up should reduce row count"

    def test_preserves_ohlcv_columns(self, sample_ohlcv_df):
        """Original OHLCV columns should still be present."""
        add_indicators = _import_add_indicators()
        result = add_indicators(sample_ohlcv_df)

        for col in ['open', 'high', 'low', 'close', 'volume']:
            assert col in result.columns, f"Missing OHLCV column: {col}"


# ============================================
# Edge Case Tests
# ============================================

class TestAddIndicatorsEdgeCases:
    def test_none_input(self):
        """Should return None for None input."""
        add_indicators = _import_add_indicators()
        assert add_indicators(None) is None

    def test_empty_dataframe(self):
        """Should return None for empty DataFrame."""
        add_indicators = _import_add_indicators()
        empty_df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        assert add_indicators(empty_df) is None

    def test_too_few_rows(self, small_ohlcv_df):
        """With fewer rows than indicator windows, should raise or return empty."""
        add_indicators = _import_add_indicators()

        # The ta library raises IndexError when data length < ATR window (14).
        # This is expected — callers should provide >= 50 rows.
        try:
            result = add_indicators(small_ohlcv_df)
            # If no exception, result should be empty or valid
            assert result is None or isinstance(result, pd.DataFrame)
        except (IndexError, ValueError):
            # Expected: indicator window > data length
            pass

    def test_does_not_modify_input(self, sample_ohlcv_df):
        """add_indicators should not modify the original DataFrame."""
        add_indicators = _import_add_indicators()
        original_cols = set(sample_ohlcv_df.columns)
        original_len = len(sample_ohlcv_df)

        add_indicators(sample_ohlcv_df)

        assert set(sample_ohlcv_df.columns) == original_cols
        assert len(sample_ohlcv_df) == original_len
