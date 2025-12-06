import time
import json
import logging
import sqlite3
import ccxt
import pandas as pd
from datetime import datetime
from utils import get_latest_data_with_indicators
from predict import predict
from strategy import Strategy

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

logging.basicConfig(filename=config['paths']['logs'], level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class PaperTrader:
    def __init__(self):
        self.strategy = Strategy()
        self.db_path = config['paths']['database']
        self.symbol = config['symbol']
        self.running = True
        self.paused = False
        
        # Initialize Balance in DB if not exists
        self.init_db_balance()
        
        # Try Binance connection
        self.exchange = None
        # In a real scenario, we'd load keys from env or secure config
        # self.exchange = ccxt.binance({
        #     'apiKey': 'YOUR_API_KEY',
        #     'secret': 'YOUR_SECRET',
        #     'enableRateLimit': True,
        #     'options': { 'defaultType': 'future' } # or spot
        # })
        # self.exchange.set_sandbox_mode(True) 
        
        if self.exchange:
            logging.info("Connected to Binance Testnet")
        else:
            logging.info("No API keys found. Using Internal Simulation Mode.")

    def init_db_balance(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM balance_history ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        if not row:
            c.execute("INSERT INTO balance_history (balance, equity) VALUES (?, ?)", 
                      (config['initial_capital'], config['initial_capital']))
            conn.commit()
        conn.close()

    def get_balance(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT balance, equity FROM balance_history ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        conn.close()
        return row[0], row[1]

    def update_balance(self, balance, equity):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO balance_history (balance, equity) VALUES (?, ?)", (balance, equity))
        conn.commit()
        conn.close()

    def log_trade(self, side, price, amount, pnl, reason, status=None):
        if status is None:
            status = 'OPEN' if side == 'BUY' else 'CLOSED'
            
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO trades (symbol, side, price, amount, cost, fee, pnl, status, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (self.symbol, side, price, amount, price*amount, 0, pnl, status, reason))
        conn.commit()
        conn.close()
        
    def log_signal(self, signal_type, prob, close):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO signals (symbol, signal_type, probability, close_price) VALUES (?, ?, ?, ?)",
                  (self.symbol, signal_type, prob, close))
        conn.commit()
        conn.close()

    def run(self):
        logging.info("Bot started.")
        
        # Track internal state for simulation
        current_balance, current_equity = self.get_balance()
        held_amount = 0
        
        while self.running:
            # Check for PAUSE command (could be file-based or DB-based)
            # For simplicity, we'll check a file 'bot_status.json' or just assume running for now
            # In a real app, API would update a status flag in DB/File.
            
            if self.paused:
                time.sleep(5)
                continue
                
            try:
                # 1. Get Prediction
                prediction = predict()
                if not prediction:
                    time.sleep(10)
                    continue
                
                current_price = prediction['close']
                self.log_signal(prediction['signal'], prediction['probability'], current_price)
                
                # 2. Strategy Decision
                decision = self.strategy.get_signal(prediction, current_price)
                
                if decision['action'] != "HOLD":
                    logging.info(f"Strategy Decision: {decision['action']} @ {current_price}")
                    
                    if decision['action'] == "BUY":
                        # Execute Buy
                        cost = current_balance * (1 - config['commission_rate'])
                        amount = cost / current_price
                        held_amount = amount
                        current_balance = 0 # All in
                        
                        self.strategy.update_position("BUY", current_price, decision['sl'], decision['tp'])
                        
                        # Log open trade (simulated)
                        # We only log CLOSED trades in the simple schema, but let's log the BUY action
                        self.log_trade("BUY", current_price, amount, 0, "SIGNAL")
                        
                    elif decision['action'] == "SELL":
                        # Execute Sell
                        revenue = held_amount * current_price * (1 - config['commission_rate'])
                        pnl = revenue - (held_amount * self.strategy.entry_price)
                        current_balance = revenue
                        held_amount = 0
                        
                        self.strategy.update_position("SELL", current_price)
                        self.log_trade("SELL", current_price, 0, pnl, decision['reason'])
                
                # Update Equity
                if self.strategy.position == "LONG":
                    current_equity = held_amount * current_price
                else:
                    current_equity = current_balance
                    
                self.update_balance(current_balance, current_equity)
                
                # Sleep
                # For 1h candles, we sleep 1h. For demo, we sleep 60s or less.
                logging.info("Waiting for next cycle...")
                time.sleep(60) 
                
            except Exception as e:
                logging.error(f"Error in main loop: {e}")
                time.sleep(10)

if __name__ == "__main__":
    bot = PaperTrader()
    bot.run()
