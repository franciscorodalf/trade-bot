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
        self.symbol = config.get('symbol', config.get('symbols', ['BTC/USDT'])[0])
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
        
        # Ensure Tables Exist
        c.execute('''CREATE TABLE IF NOT EXISTS balance_history
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      balance REAL, equity REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS trades
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      symbol TEXT, side TEXT, price REAL, amount REAL, cost REAL, fee REAL, pnl REAL, status TEXT, reason TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS signals
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      symbol TEXT, signal_type TEXT, probability REAL, close_price REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
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
        if row:
            return row[0], row[1]
        return config['initial_capital'], config['initial_capital']

    def update_balance(self, balance, equity):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO balance_history (balance, equity) VALUES (?, ?)", (balance, equity))
        conn.commit()
        conn.close()

    def log_trade(self, side, price, amount, pnl, reason, cost=0, fee=0, status=None, symbol=None):
        if status is None:
            status = 'OPEN' if side == 'BUY' else 'CLOSED'
            
        trade_symbol = symbol if symbol else self.symbol
            
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO trades (symbol, side, price, amount, cost, fee, pnl, status, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (trade_symbol, side, price, amount, cost, fee, pnl, status, reason))
        conn.commit()
        conn.close()
        
    def log_signal(self, signal_type, probability, close_price, symbol=None):
        trade_symbol = symbol if symbol else self.symbol
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO signals (symbol, signal_type, probability, close_price) VALUES (?, ?, ?, ?)", 
                  (trade_symbol, signal_type, probability, close_price))
        conn.commit()
        conn.close()

    def load_portfolio(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        # Load OPEN trades
        c.execute("SELECT symbol, amount, price FROM trades WHERE status='OPEN'")
        rows = c.fetchall()
        for r in rows:
            sym, amt, price = r
            # We don't have SL/TP in DB, so we use defaults or wide limits
            self.portfolio[sym] = (amt, price, 0, 999999) 
            logging.info(f"Loaded open position from DB: {sym} ({amt} units @ {price})")
        conn.close()

    def run(self):
        logging.info("Bot started in Multi-Symbol Mode.")
        
        # Track internal state for simulation
        current_balance, current_equity = self.get_balance()
        
        # Portfolio State: { "SYMBOL": (amount, entry_price, sl, tp) }
        self.portfolio = {}
        try:
            self.load_portfolio()
        except Exception as e:
            logging.error(f"Failed to load portfolio: {e}")
            
        portfolio = self.portfolio # Alias
        
        while self.running:
            if self.paused:
                time.sleep(5)
                continue
                
            try:
                symbols = config.get('symbols', [config.get('symbol')])
                max_pos = config.get('max_open_positions', 3)
                
                opportunities = []
                
                # 1. SCANNING PHASE
                logging.info(f"Scanning market... ({len(symbols)} pairs)")
                
                for symbol in symbols:
                    from predict import predict_symbol
                    prediction = predict_symbol(symbol)
                    
                    if not prediction:
                        continue
                        
                    current_price = prediction['close']
                    self.log_signal(prediction['signal'], prediction['probability'], current_price, symbol=symbol)
                    
                    opportunities.append({
                        "symbol": symbol,
                        "prediction": prediction,
                        "price": current_price
                    })
                    
                # 2. RANKING PHASE
                buy_signals = [o for o in opportunities if o['prediction']['signal'] == "BUY"]
                buy_signals.sort(key=lambda x: x['prediction']['probability'], reverse=True)
                
                logging.info(f"Found {len(buy_signals)} BUY opportunities.")
                
                # 3. EXECUTION PHASE
                
                # Manage Exits
                for symbol in list(portfolio.keys()):
                    opp = next((o for o in opportunities if o['symbol'] == symbol), None)
                    if not opp: continue
                    
                    current_price = opp['price']
                    prediction = opp['prediction']
                    
                    amount, entry_price, sl_price, tp_price = portfolio[symbol]
                    
                    exit_reason = None
                    if sl_price > 0 and current_price <= sl_price: exit_reason = "SL"
                    elif tp_price < 999999 and current_price >= tp_price: exit_reason = "TP"
                    elif prediction['signal'] == "SELL": exit_reason = "SIGNAL_FLIP"
                    
                    if exit_reason:
                        revenue = amount * current_price * (1 - config['commission_rate'])
                        pnl = revenue - (amount * entry_price)
                        current_balance += revenue
                        del portfolio[symbol]
                        
                        sell_fee = revenue * config['commission_rate']
                        current_balance -= sell_fee # Deduct sell fee from balance (PnL calculation might need adjustment if PnL includes fee)
                        # PnL = (Revenue - Sell Fee) - (Cost + Buy Fee). My PnL calc above was simple.
                        # Let's keep PnL simple: Revenue - Cost. Fees are logged separately.
                        
                        self.log_trade("SELL", current_price, amount, pnl, exit_reason, cost=portfolio[symbol][0]*portfolio[symbol][1], fee=sell_fee, symbol=symbol)
                        logging.info(f"SELL {symbol} ({exit_reason}). PnL: {pnl:.2f}")

                # Enter New Positions
                open_slots = max_pos - len(portfolio)
                
                if open_slots > 0:
                    for opp in buy_signals:
                        if open_slots <= 0: break
                        symbol = opp['symbol']
                        if symbol in portfolio: continue
                        
                        prediction = opp['prediction']
                        current_price = opp['price']
                        
                        # Capital Allocation
                        position_size_usdt = config['initial_capital'] / max_pos
                        if position_size_usdt > current_balance:
                            position_size_usdt = current_balance * 0.98
                        
                        if position_size_usdt < 5: continue
                            
                        amount = position_size_usdt / current_price
                        cost = amount * current_price
                        fee = cost * config['commission_rate']
                        
                        if (cost + fee) > current_balance:
                            amount = current_balance / (current_price * (1 + config['commission_rate']))
                            amount *= 0.999 # Safety
                            cost = amount * current_price
                            fee = cost * config['commission_rate']
                        
                        if amount > 0 and cost > 5:
                            current_balance -= (cost + fee)
                            sl, tp = self.strategy.calculate_sl_tp(current_price, "BUY", prediction.get('atr', 0))
                            
                            portfolio[symbol] = (amount, current_price, sl, tp)
                            open_slots -= 1
                            
                            self.log_trade("BUY", current_price, amount, 0, "SIGNAL", cost=cost, fee=fee, symbol=symbol)
                            logging.info(f"BUY {symbol} @ {current_price:.8f}. Prob: {prediction['probability']:.2f}")

                # Update Equity
                equity_positions = 0
                for sym, (amt, price, _, _) in portfolio.items():
                    opp = next((o for o in opportunities if o['symbol'] == sym), None)
                    if opp:
                        equity_positions += amt * opp['price']
                    else:
                        equity_positions += amt * price
                
                current_equity = current_balance + equity_positions
                self.update_balance(current_balance, current_equity)
                
                logging.info(f"Cycle End. Balance: {current_balance:.2f}, Equity: {current_equity:.2f}. Open Pos: {len(portfolio)}")
                
                time.sleep(60) 
                
            except Exception as e:
                logging.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(10)

if __name__ == "__main__":
    bot = PaperTrader()
    bot.run()
