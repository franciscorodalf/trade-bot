import json
import logging

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

class Strategy:
    def __init__(self):
        self.position = "NONE" # NONE, LONG
        self.entry_price = 0.0
        self.sl_price = 0.0
        self.tp_price = 0.0
        self.risk_per_trade = config['risk_per_trade']
        self.commission_rate = config['commission_rate']
        self.slippage = config['slippage']
        
    def calculate_sl_tp(self, entry_price, signal_type, atr):
        """
        Calculate Stop Loss and Take Profit prices using ATR.
        """
        # ATR Multipliers
        sl_mult = 1.5 # Tighter stop
        tp_mult = 2.5 # Reward > Risk
        
        # Fallback if ATR is 0 or None (shouldn't happen with valid data)
        if not atr or atr == 0:
            risk_pct = 0.02
            reward_pct = 0.03
            if signal_type == "BUY":
                return entry_price * (1 - risk_pct), entry_price * (1 + reward_pct)
        
        if signal_type == "BUY":
            sl = entry_price - (atr * sl_mult)
            tp = entry_price + (atr * tp_mult)
            return sl, tp
        return 0.0, 0.0

    def check_exit(self, current_price):
        """
        Check if SL or TP is hit.
        """
        if self.position == "LONG":
            if current_price <= self.sl_price:
                return "SL"
            if current_price >= self.tp_price:
                return "TP"
        return None

    def get_signal(self, prediction, current_price):
        """
        Decide whether to enter, exit, or hold based on prediction and current state.
        """
        signal_type = prediction['signal']
        prob = prediction['probability']
        atr = prediction.get('atr', 0.0)
        
        # Check for exit signals first (SL/TP)
        exit_reason = self.check_exit(current_price)
        if exit_reason:
            return {
                "action": "SELL",
                "reason": exit_reason,
                "price": current_price
            }
            
        # Entry Logic
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
        
        # Exit Logic based on model (optional, if model flips to SELL)
        elif self.position == "LONG":
            if signal_type == "SELL":
                 return {
                    "action": "SELL",
                    "reason": "SIGNAL_FLIP",
                    "price": current_price
                }
                
        return {"action": "HOLD"}

    def update_position(self, action, price, sl=0.0, tp=0.0):
        """
        Update internal state after a trade execution.
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
