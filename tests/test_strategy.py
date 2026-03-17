"""
Tests for the Strategy module.
Covers: SL/TP calculation, exit detection, signal logic, position management.
"""

import pytest
import json
import sys
import os

# We need to mock config.json before importing Strategy
# since it loads config at module level.


@pytest.fixture(autouse=True)
def mock_config(monkeypatch, config_file, config_with_paths):
    """Ensure Strategy module loads our test config."""
    original_dir = os.getcwd()
    os.chdir(os.path.dirname(config_file))
    sys.path.insert(0, os.path.join(os.path.dirname(config_file), '..', 'bot'))
    yield
    os.chdir(original_dir)


def _make_strategy():
    """Import and create a fresh Strategy instance (after config is mocked)."""
    # Force reimport to pick up the mocked config
    if 'strategy' in sys.modules:
        del sys.modules['strategy']
    from strategy import Strategy
    return Strategy()


# ============================================
# SL/TP Calculation Tests
# ============================================

class TestCalculateSlTp:
    def test_buy_with_valid_atr(self):
        """SL/TP should use ATR multipliers (1.5x SL, 2.5x TP)."""
        strategy = _make_strategy()
        entry = 50000.0
        atr = 500.0

        sl, tp = strategy.calculate_sl_tp(entry, "BUY", atr)

        assert sl == entry - (atr * 1.5)  # 49250
        assert tp == entry + (atr * 2.5)  # 51250
        assert sl < entry < tp

    def test_buy_sl_tp_ordering(self):
        """SL must always be below entry, TP above."""
        strategy = _make_strategy()
        for price in [100, 1000, 50000, 0.05]:
            sl, tp = strategy.calculate_sl_tp(price, "BUY", price * 0.01)
            assert sl < price, f"SL {sl} should be < entry {price}"
            assert tp > price, f"TP {tp} should be > entry {price}"

    def test_buy_with_zero_atr_uses_fallback(self):
        """When ATR is 0, should use percentage-based fallback."""
        strategy = _make_strategy()
        entry = 50000.0

        sl, tp = strategy.calculate_sl_tp(entry, "BUY", 0)

        assert sl == entry * 0.98  # 2% fallback SL
        assert tp == entry * 1.03  # 3% fallback TP

    def test_buy_with_none_atr_uses_fallback(self):
        """When ATR is None, should use percentage-based fallback."""
        strategy = _make_strategy()
        entry = 1000.0

        sl, tp = strategy.calculate_sl_tp(entry, "BUY", None)

        assert sl == entry * 0.98
        assert tp == entry * 1.03

    def test_non_buy_returns_zeros(self):
        """Non-BUY signals should return 0.0 for both SL and TP."""
        strategy = _make_strategy()

        sl, tp = strategy.calculate_sl_tp(50000, "SELL", 500)

        assert sl == 0.0
        assert tp == 0.0

    def test_atr_proportional_to_volatility(self):
        """Higher ATR should produce wider SL/TP bands."""
        strategy = _make_strategy()
        entry = 50000.0

        sl_low, tp_low = strategy.calculate_sl_tp(entry, "BUY", 100)
        sl_high, tp_high = strategy.calculate_sl_tp(entry, "BUY", 1000)

        # Higher ATR = wider bands
        assert (entry - sl_high) > (entry - sl_low)
        assert (tp_high - entry) > (tp_low - entry)


# ============================================
# Exit Detection Tests
# ============================================

class TestCheckExit:
    def test_sl_triggered(self):
        """Should return 'SL' when price drops to stop loss."""
        strategy = _make_strategy()
        strategy.position = "LONG"
        strategy.sl_price = 49000.0
        strategy.tp_price = 52000.0

        assert strategy.check_exit(48500.0) == "SL"
        assert strategy.check_exit(49000.0) == "SL"

    def test_tp_triggered(self):
        """Should return 'TP' when price reaches take profit."""
        strategy = _make_strategy()
        strategy.position = "LONG"
        strategy.sl_price = 49000.0
        strategy.tp_price = 52000.0

        assert strategy.check_exit(52000.0) == "TP"
        assert strategy.check_exit(55000.0) == "TP"

    def test_no_exit_in_range(self):
        """Should return None when price is between SL and TP."""
        strategy = _make_strategy()
        strategy.position = "LONG"
        strategy.sl_price = 49000.0
        strategy.tp_price = 52000.0

        assert strategy.check_exit(50000.0) is None
        assert strategy.check_exit(51999.99) is None

    def test_no_exit_when_no_position(self):
        """Should return None when not in a position."""
        strategy = _make_strategy()
        strategy.position = "NONE"

        assert strategy.check_exit(100.0) is None


# ============================================
# Signal Decision Tests
# ============================================

class TestGetSignal:
    def test_buy_signal_when_no_position(self):
        """Should return BUY action when model predicts BUY and no position open."""
        strategy = _make_strategy()
        strategy.position = "NONE"

        prediction = {"signal": "BUY", "probability": 0.72, "atr": 500.0}
        result = strategy.get_signal(prediction, 50000.0)

        assert result["action"] == "BUY"
        assert result["reason"] == "SIGNAL"
        assert "sl" in result
        assert "tp" in result

    def test_hold_when_no_signal(self):
        """Should HOLD when model predicts HOLD."""
        strategy = _make_strategy()
        strategy.position = "NONE"

        prediction = {"signal": "HOLD", "probability": 0.50, "atr": 500.0}
        result = strategy.get_signal(prediction, 50000.0)

        assert result["action"] == "HOLD"

    def test_sell_on_sl_hit(self):
        """Should SELL with SL reason when stop loss is hit."""
        strategy = _make_strategy()
        strategy.position = "LONG"
        strategy.sl_price = 49000.0
        strategy.tp_price = 52000.0

        prediction = {"signal": "BUY", "probability": 0.80, "atr": 500.0}
        result = strategy.get_signal(prediction, 48000.0)

        assert result["action"] == "SELL"
        assert result["reason"] == "SL"

    def test_sell_on_tp_hit(self):
        """Should SELL with TP reason when take profit is hit."""
        strategy = _make_strategy()
        strategy.position = "LONG"
        strategy.sl_price = 49000.0
        strategy.tp_price = 52000.0

        prediction = {"signal": "BUY", "probability": 0.80, "atr": 500.0}
        result = strategy.get_signal(prediction, 53000.0)

        assert result["action"] == "SELL"
        assert result["reason"] == "TP"

    def test_sell_on_signal_flip(self):
        """Should SELL when model flips from LONG to SELL."""
        strategy = _make_strategy()
        strategy.position = "LONG"
        strategy.sl_price = 40000.0
        strategy.tp_price = 60000.0

        prediction = {"signal": "SELL", "probability": 0.30, "atr": 500.0}
        result = strategy.get_signal(prediction, 50000.0)

        assert result["action"] == "SELL"
        assert result["reason"] == "SIGNAL_FLIP"

    def test_sl_takes_priority_over_signal_flip(self):
        """SL exit should take priority over signal-based exit."""
        strategy = _make_strategy()
        strategy.position = "LONG"
        strategy.sl_price = 49000.0
        strategy.tp_price = 52000.0

        prediction = {"signal": "SELL", "probability": 0.30, "atr": 500.0}
        result = strategy.get_signal(prediction, 48000.0)

        assert result["action"] == "SELL"
        assert result["reason"] == "SL"  # SL takes priority


# ============================================
# Position Management Tests
# ============================================

class TestUpdatePosition:
    def test_buy_updates_state(self):
        """BUY should set position to LONG with entry, SL, TP."""
        strategy = _make_strategy()
        strategy.update_position("BUY", 50000.0, sl=49000.0, tp=52000.0)

        assert strategy.position == "LONG"
        assert strategy.entry_price == 50000.0
        assert strategy.sl_price == 49000.0
        assert strategy.tp_price == 52000.0

    def test_sell_clears_state(self):
        """SELL should reset all position state."""
        strategy = _make_strategy()
        strategy.update_position("BUY", 50000.0, sl=49000.0, tp=52000.0)
        strategy.update_position("SELL", 51000.0)

        assert strategy.position == "NONE"
        assert strategy.entry_price == 0.0
        assert strategy.sl_price == 0.0
        assert strategy.tp_price == 0.0

    def test_full_lifecycle(self):
        """Test complete: NONE -> BUY -> check exits -> SELL -> NONE."""
        strategy = _make_strategy()

        # Initial state
        assert strategy.position == "NONE"

        # Enter position
        strategy.update_position("BUY", 50000.0, sl=49000.0, tp=52000.0)
        assert strategy.position == "LONG"

        # Price within range
        assert strategy.check_exit(50500.0) is None

        # TP hit
        assert strategy.check_exit(52500.0) == "TP"

        # Close position
        strategy.update_position("SELL", 52500.0)
        assert strategy.position == "NONE"
