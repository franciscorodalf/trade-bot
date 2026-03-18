"""Tests for the Strategy and bet sizing modules."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))

from bet_sizing import calculate_kelly, calculate_edge, size_bet, calculate_expected_value


class TestKellyCriterion:
    def test_positive_edge(self):
        """Kelly should return positive fraction when model has edge."""
        frac = calculate_kelly(0.65, 0.50, kelly_fraction=1.0)
        assert frac > 0

    def test_no_edge(self):
        """Kelly should return 0 when model equals market."""
        frac = calculate_kelly(0.50, 0.50, kelly_fraction=1.0)
        assert frac == 0

    def test_negative_edge(self):
        """Kelly should return 0 when model is worse than market."""
        frac = calculate_kelly(0.40, 0.50, kelly_fraction=1.0)
        assert frac == 0

    def test_fractional_kelly(self):
        """Fractional Kelly should be smaller than full Kelly."""
        full = calculate_kelly(0.65, 0.50, kelly_fraction=1.0)
        frac = calculate_kelly(0.65, 0.50, kelly_fraction=0.25)
        assert frac < full

    def test_max_cap(self):
        """Kelly should be capped at 15%."""
        frac = calculate_kelly(0.95, 0.10, kelly_fraction=1.0)
        assert frac <= 0.15

    def test_invalid_market_price(self):
        """Should return 0 for invalid market prices."""
        assert calculate_kelly(0.60, 0.0) == 0
        assert calculate_kelly(0.60, 1.0) == 0


class TestEdgeCalculation:
    def test_positive_edge(self):
        edge = calculate_edge(0.65, 0.50)
        assert abs(edge - 0.15) < 1e-10

    def test_negative_edge(self):
        edge = calculate_edge(0.40, 0.50)
        assert abs(edge - (-0.10)) < 1e-10

    def test_zero_edge(self):
        edge = calculate_edge(0.50, 0.50)
        assert edge == 0


class TestExpectedValue:
    def test_positive_ev(self):
        ev = calculate_expected_value(0.65, 0.50, 10.0)
        assert ev > 0

    def test_negative_ev(self):
        ev = calculate_expected_value(0.40, 0.50, 10.0)
        assert ev < 0


class TestBetSizing:
    def test_bet_when_edge_exists(self):
        """Should return bet when model has edge above threshold."""
        result = size_bet(0.65, 0.50, 100.0, "UP")
        assert result is not None
        assert result["side"] == "UP"
        assert result["bet_amount"] > 0
        assert result["edge"] > 0

    def test_no_bet_when_no_edge(self):
        """Should return None when edge below threshold."""
        result = size_bet(0.51, 0.50, 100.0, "UP")
        assert result is None

    def test_bet_amount_within_limits(self):
        """Bet should respect min/max limits."""
        result = size_bet(0.70, 0.50, 100.0, "UP")
        assert result is not None
        assert result["bet_amount"] >= 1.0
        assert result["bet_amount"] <= 25.0

    def test_down_side_bet(self):
        """Should correctly size DOWN bets."""
        result = size_bet(0.35, 0.50, 100.0, "DOWN")
        assert result is not None
        assert result["side"] == "DOWN"

    def test_low_bankroll(self):
        """Should return None when bankroll too low."""
        result = size_bet(0.65, 0.50, 0.50, "UP")
        assert result is None
