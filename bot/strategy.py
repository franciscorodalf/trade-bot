"""
Trading strategy and risk management engine.

Implements ATR-based dynamic stop loss / take profit calculation,
position management, and trade signal generation.
"""

import json
import logging
from typing import Dict, Optional, Tuple, Any

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

# ATR multipliers for SL/TP (Risk:Reward = 1.5:2.5)
SL_ATR_MULTIPLIER: float = 1.5
TP_ATR_MULTIPLIER: float = 2.5

# Fallback percentages when ATR is unavailable
FALLBACK_SL_PCT: float = 0.02  # 2%
FALLBACK_TP_PCT: float = 0.03  # 3%


class Strategy:
    """
    Manages trade lifecycle: entry signals, exit conditions, and position state.

    The strategy uses ATR-based dynamic stops that adapt to market volatility.
    Wider stops in volatile markets (to avoid premature exits) and tighter
    stops in calm markets (to protect capital).
    """

    def __init__(self) -> None:
        self.position: str = "NONE"  # NONE or LONG
        self.entry_price: float = 0.0
        self.sl_price: float = 0.0
        self.tp_price: float = 0.0
        self.risk_per_trade: float = config['risk_per_trade']
        self.commission_rate: float = config['commission_rate']
        self.slippage: float = config['slippage']

    def calculate_sl_tp(
        self,
        entry_price: float,
        signal_type: str,
        atr: Optional[float]
    ) -> Tuple[float, float]:
        """
        Calculate Stop Loss and Take Profit using ATR multiples.

        Args:
            entry_price: The price at which the position is entered.
            signal_type: 'BUY' for long entries.
            atr: Average True Range value. Falls back to % if None/0.

        Returns:
            Tuple of (stop_loss_price, take_profit_price).
            Returns (0.0, 0.0) for non-BUY signals.
        """
        # Fallback to percentage-based stops if ATR unavailable
        if not atr or atr == 0:
            if signal_type == "BUY":
                return entry_price * (1 - FALLBACK_SL_PCT), entry_price * (1 + FALLBACK_TP_PCT)

        if signal_type == "BUY":
            sl = entry_price - (atr * SL_ATR_MULTIPLIER)
            tp = entry_price + (atr * TP_ATR_MULTIPLIER)
            return sl, tp
        return 0.0, 0.0

    def check_exit(self, current_price: float) -> Optional[str]:
        """
        Check if current price triggers a stop loss or take profit exit.

        Args:
            current_price: The current market price.

        Returns:
            'SL' if stop loss hit, 'TP' if take profit hit, None otherwise.
        """
        if self.position == "LONG":
            if current_price <= self.sl_price:
                return "SL"
            if current_price >= self.tp_price:
                return "TP"
        return None

    def get_signal(
        self,
        prediction: Dict[str, Any],
        current_price: float
    ) -> Dict[str, Any]:
        """
        Generate a trade action based on ML prediction and current state.

        Priority order:
        1. SL/TP exits (risk management overrides everything)
        2. Signal-based exit (model flips to SELL while in LONG)
        3. New entry (model signals BUY while no position)
        4. HOLD (no action)

        Args:
            prediction: Dict with keys 'signal', 'probability', 'atr'.
            current_price: Current market price.

        Returns:
            Dict with 'action' ('BUY'/'SELL'/'HOLD') and optional metadata.
        """
        signal_type: str = prediction['signal']
        atr: float = prediction.get('atr', 0.0)

        # Priority 1: Check SL/TP exits
        exit_reason = self.check_exit(current_price)
        if exit_reason:
            return {
                "action": "SELL",
                "reason": exit_reason,
                "price": current_price
            }

        # Priority 2: New entry when flat
        if self.position == "NONE":
            if signal_type == "BUY":
                sl, tp = self.calculate_sl_tp(current_price, "BUY", atr)
                return {
                    "action": "BUY",
                    "reason": "SIGNAL",
                    "price": current_price,
                    "sl": sl,
                    "tp": tp
                }

        # Priority 3: Signal-based exit
        elif self.position == "LONG":
            if signal_type == "SELL":
                return {
                    "action": "SELL",
                    "reason": "SIGNAL_FLIP",
                    "price": current_price
                }

        return {"action": "HOLD"}

    def update_position(
        self,
        action: str,
        price: float,
        sl: float = 0.0,
        tp: float = 0.0
    ) -> None:
        """
        Update internal position state after trade execution.

        Args:
            action: 'BUY' to open, 'SELL' to close.
            price: Execution price.
            sl: Stop loss price (only for BUY).
            tp: Take profit price (only for BUY).
        """
        if action == "BUY":
            self.position = "LONG"
            self.entry_price = price
            self.sl_price = sl
            self.tp_price = tp
        elif action == "SELL":
            self.position = "NONE"
            self.entry_price = 0.0
            self.sl_price = 0.0
            self.tp_price = 0.0
