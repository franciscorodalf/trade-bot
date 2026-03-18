"""
Bet sizing using fractional Kelly Criterion.

Calculates optimal bet size based on the edge between
the model's calibrated probability and the market price.
"""

import json
import logging
import os
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")
with open(_config_path, "r") as f:
    config = json.load(f)


def calculate_kelly(
    predicted_prob: float,
    market_price: float,
    kelly_fraction: Optional[float] = None,
) -> float:
    """
    Calculate fractional Kelly bet size.

    Full Kelly maximizes expected log-wealth but has high variance.
    Fractional Kelly (typically 0.25x) reduces variance at the cost
    of slower growth — much safer for real money.

    Args:
        predicted_prob: Model's calibrated probability of the outcome (0-1).
        market_price: Current market price / implied probability (0-1).
        kelly_fraction: Fraction of full Kelly to use (default from config).

    Returns:
        Fraction of bankroll to bet (0-1). Returns 0 if no edge.
    """
    if kelly_fraction is None:
        kelly_fraction = config["trading"]["kelly_fraction"]

    # Odds in decimal format
    # If market price is 0.40, buying YES at 0.40 pays 1/0.40 = 2.5x
    if market_price <= 0 or market_price >= 1:
        return 0.0

    # Decimal odds (what you get back per $1 bet, including stake)
    decimal_odds = 1.0 / market_price

    # Net odds (profit per $1 bet)
    b = decimal_odds - 1.0

    # Kelly formula: f* = (p * b - q) / b
    # where p = prob of winning, q = 1-p, b = net odds
    p = predicted_prob
    q = 1.0 - p

    full_kelly = (p * b - q) / b

    # No edge → no bet
    if full_kelly <= 0:
        return 0.0

    # Apply fractional Kelly
    fractional = full_kelly * kelly_fraction

    # Cap at reasonable maximum (never bet more than 15% of bankroll)
    return min(fractional, 0.15)


def calculate_edge(predicted_prob: float, market_price: float) -> float:
    """
    Calculate the edge: difference between model probability and market price.

    A positive edge means the model thinks the outcome is more likely
    than the market implies.

    Args:
        predicted_prob: Model's calibrated probability (0-1).
        market_price: Market implied probability / price (0-1).

    Returns:
        Edge as a decimal (e.g., 0.10 = 10% edge).
    """
    return predicted_prob - market_price


def calculate_expected_value(
    predicted_prob: float,
    market_price: float,
    bet_amount: float,
) -> float:
    """
    Calculate expected value of a bet.

    Args:
        predicted_prob: Model probability of winning.
        market_price: Price paid per share.
        bet_amount: Amount in USDC to bet.

    Returns:
        Expected profit/loss in USDC.
    """
    shares = bet_amount / market_price
    payout_if_win = shares * 1.0  # Each share pays $1 if correct
    cost = bet_amount

    ev = (predicted_prob * payout_if_win) - cost
    return ev


def size_bet(
    predicted_prob: float,
    market_price: float,
    bankroll: float,
    side: str,
) -> Optional[Dict[str, Any]]:
    """
    Full bet sizing decision: should we bet, and how much?

    Args:
        predicted_prob: Calibrated probability of BTC going UP.
        market_price: Current YES (UP) price on Polymarket.
        bankroll: Current available capital in USDC.
        side: "UP" or "DOWN" — which side to evaluate.

    Returns:
        Dict with bet details, or None if no bet should be placed.
    """
    min_edge = config["trading"]["min_edge"]
    min_bet = config["trading"]["min_bet"]
    max_bet = config["trading"]["max_bet"]

    # Determine effective probability and price based on side
    if side == "UP":
        prob = predicted_prob
        price = market_price
    else:  # DOWN
        prob = 1.0 - predicted_prob
        price = 1.0 - market_price

    # Calculate edge
    edge = calculate_edge(prob, price)

    # No edge or edge below minimum threshold
    if edge < min_edge:
        return None

    # Kelly sizing
    kelly_frac = calculate_kelly(prob, price)
    if kelly_frac <= 0:
        return None

    # Calculate bet amount
    bet_amount = bankroll * kelly_frac
    bet_amount = max(bet_amount, min_bet)
    bet_amount = min(bet_amount, max_bet)
    bet_amount = min(bet_amount, bankroll * 0.95)  # Never bet more than 95% of bankroll

    if bet_amount < min_bet:
        return None

    # Expected value
    ev = calculate_expected_value(prob, price, bet_amount)

    return {
        "side": side,
        "bet_amount": round(bet_amount, 2),
        "edge": round(edge, 4),
        "kelly_fraction": round(kelly_frac, 4),
        "predicted_prob": round(prob, 4),
        "market_price": round(price, 4),
        "expected_value": round(ev, 4),
        "shares": round(bet_amount / price, 4),
        "potential_profit": round((bet_amount / price) - bet_amount, 2),
    }
