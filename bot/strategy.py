"""
Betting strategy with edge detection for Polymarket BTC predictions.

Decides WHEN to bet (edge threshold), WHICH SIDE (UP/DOWN),
and HOW MUCH (via Kelly criterion), with risk management rules.
"""

import json
import logging
import os
import time
from typing import Dict, Optional, Any, List

from bet_sizing import size_bet, calculate_edge

logger = logging.getLogger(__name__)

_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")
with open(_config_path, "r") as f:
    config = json.load(f)


class Strategy:
    """
    Edge-based betting strategy for Polymarket BTC 5-minute markets.

    Decision flow:
    1. Get model prediction (calibrated probability of BTC going UP)
    2. Get market price (implied probability)
    3. Calculate edge = model_prob - market_prob
    4. If edge > min_threshold → bet using Kelly sizing
    5. Apply risk limits (max bets, cooldowns, bankroll protection)
    """

    def __init__(self) -> None:
        self.min_edge: float = config["trading"]["min_edge"]
        self.max_open_bets: int = config["trading"]["max_open_bets"]
        self.cooldown_seconds: float = config["trading"]["cooldown_after_loss_seconds"]
        self.min_confidence: float = 0.05  # Minimum |prob - 0.5|

        # State
        self.open_bets: List[Dict[str, Any]] = []
        self.last_loss_time: float = 0
        self.consecutive_losses: int = 0
        self.total_bets: int = 0
        self.total_wins: int = 0

    def evaluate(
        self,
        prediction: Dict[str, Any],
        market_yes_price: float,
        bankroll: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate whether to place a bet given current prediction and market.

        Args:
            prediction: Output from Predictor.predict() with calibrated_probability.
            market_yes_price: Current YES (UP) price on Polymarket (0-1).
            bankroll: Available capital in USDC.

        Returns:
            Bet decision dict if we should bet, None otherwise.
        """
        cal_prob = prediction["calibrated_probability"]
        confidence = prediction["confidence"]

        # ---- Risk Management Checks ----

        # 1. Maximum open bets
        if len(self.open_bets) >= self.max_open_bets:
            logger.debug("Max open bets reached. Skipping.")
            return None

        # 2. Cooldown after losses
        if self._in_cooldown():
            remaining = self.cooldown_seconds - (time.time() - self.last_loss_time)
            logger.debug(f"In cooldown. {remaining:.0f}s remaining.")
            return None

        # 3. Minimum confidence (model must be somewhat sure)
        if confidence < self.min_confidence:
            logger.debug(f"Low confidence ({confidence:.3f}). Skipping.")
            return None

        # 4. Bankroll protection
        if bankroll < config["trading"]["min_bet"]:
            logger.warning(f"Bankroll too low (${bankroll:.2f}). Cannot bet.")
            return None

        # ---- Edge Detection ----

        # Evaluate both sides and pick the one with more edge
        up_edge = calculate_edge(cal_prob, market_yes_price)
        down_edge = calculate_edge(1 - cal_prob, 1 - market_yes_price)

        # Pick the side with more edge
        if up_edge > down_edge and up_edge >= self.min_edge:
            bet = size_bet(cal_prob, market_yes_price, bankroll, "UP")
        elif down_edge > up_edge and down_edge >= self.min_edge:
            bet = size_bet(cal_prob, market_yes_price, bankroll, "DOWN")
        else:
            logger.debug(
                f"No sufficient edge. UP={up_edge:.3f}, DOWN={down_edge:.3f} "
                f"(min={self.min_edge})"
            )
            return None

        if bet is None:
            return None

        # Enrich with prediction metadata
        bet["model_probability_up"] = cal_prob
        bet["market_price_yes"] = market_yes_price
        bet["raw_probability"] = prediction.get("raw_probability", 0)
        bet["features_used"] = prediction.get("features_used", 0)

        logger.info(
            f"BET SIGNAL: {bet['side']} ${bet['bet_amount']:.2f} | "
            f"Edge={bet['edge']:.1%} | Kelly={bet['kelly_fraction']:.3f} | "
            f"EV=${bet['expected_value']:.2f}"
        )

        return bet

    def record_result(self, bet_id: str, won: bool, pnl: float) -> None:
        """Record the result of a resolved bet."""
        self.total_bets += 1
        if won:
            self.total_wins += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.last_loss_time = time.time()

        # Remove from open bets
        self.open_bets = [b for b in self.open_bets if b.get("id") != bet_id]

        logger.info(
            f"Bet resolved: {'WIN' if won else 'LOSS'} ${pnl:+.2f} | "
            f"Record: {self.total_wins}/{self.total_bets} "
            f"({self.win_rate:.1%})"
        )

    def add_open_bet(self, bet: Dict[str, Any]) -> None:
        """Track a new open bet."""
        self.open_bets.append(bet)

    @property
    def win_rate(self) -> float:
        """Current win rate."""
        return self.total_wins / self.total_bets if self.total_bets > 0 else 0

    def _in_cooldown(self) -> bool:
        """Check if we're in a cooldown period after consecutive losses."""
        if self.consecutive_losses < 3:
            return False
        return (time.time() - self.last_loss_time) < self.cooldown_seconds

    def get_stats(self) -> Dict[str, Any]:
        """Return current strategy statistics."""
        return {
            "total_bets": self.total_bets,
            "total_wins": self.total_wins,
            "win_rate": round(self.win_rate, 4),
            "open_bets": len(self.open_bets),
            "consecutive_losses": self.consecutive_losses,
            "in_cooldown": self._in_cooldown(),
        }
