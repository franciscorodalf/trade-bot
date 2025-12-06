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
        
    def calculate_sl_tp(self, entry_price, signal_type):
        """
        Calculate Stop Loss and Take Profit prices.
        """
        # Simple risk reward 1:1.5 or similar, or based on ATR if we had it.
        # Using fixed percentage for now as per plan.
        risk_pct = 0.02 # 2% risk
        reward_pct = 0.03 # 3% reward
        
        if signal_type == "BUY":
            sl = entry_price * (1 - risk_pct)
            tp = entry_price * (1 + reward_pct)
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
                sl, tp = self.calculate_sl_tp(current_price, "BUY")
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
