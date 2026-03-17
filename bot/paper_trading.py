"""
Paper trading engine — the main execution loop.

Continuously scans configured cryptocurrency pairs, generates ML predictions,
manages a simulated portfolio with position entries/exits, and persists
all state to SQLite for the dashboard to display.
"""

import time
import json
import logging
import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from contextlib import contextmanager

from strategy import Strategy

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

logging.basicConfig(
    filename=config['paths']['logs'],
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Constants
MIN_TRADE_VALUE_USDT: float = 5.0
SAFETY_MARGIN: float = 0.999
SCAN_INTERVAL_SECONDS: int = 60
PAUSE_CHECK_SECONDS: int = 5

# Type alias for portfolio positions
# (amount, entry_price, stop_loss, take_profit)
Position = Tuple[float, float, float, float]


class PaperTrader:
    """
    Simulated trading engine with real market data.

    Executes a scan → rank → trade cycle every 60 seconds:
    1. Fetch ML predictions for all configured symbols
    2. Manage exits on open positions (SL/TP/signal flip)
    3. Enter new positions on highest-confidence BUY signals
    4. Update portfolio equity and persist to database
    """

    def __init__(self) -> None:
        self.strategy = Strategy()
        self.db_path: str = config['paths']['database']
        self.running: bool = True
        self.portfolio: Dict[str, Position] = {}

        # Initialize database schema and starting balance
        self._init_database()
        logging.info("Paper Trading engine initialized. Mode: Simulation.")

    # ---- Database Operations ----

    @contextmanager
    def _get_db(self):
        """Context manager for safe database access."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_database(self) -> None:
        """Create tables if they don't exist and seed initial balance."""
        with self._get_db() as conn:
            c = conn.cursor()

            c.execute('''CREATE TABLE IF NOT EXISTS balance_history
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          balance REAL, equity REAL,
                          timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

            c.execute('''CREATE TABLE IF NOT EXISTS trades
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          symbol TEXT, side TEXT, price REAL, amount REAL,
                          cost REAL, fee REAL, pnl REAL, status TEXT,
                          reason TEXT,
                          timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

            c.execute('''CREATE TABLE IF NOT EXISTS signals
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          symbol TEXT, signal_type TEXT, probability REAL,
                          close_price REAL,
                          timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

            # Seed balance if first run
            row = c.execute(
                "SELECT * FROM balance_history ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not row:
                capital = config['initial_capital']
                c.execute(
                    "INSERT INTO balance_history (balance, equity) VALUES (?, ?)",
                    (capital, capital)
                )

    def _get_balance(self) -> Tuple[float, float]:
        """Read latest balance and equity from database."""
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT balance, equity FROM balance_history ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row:
            return row['balance'], row['equity']
        capital = config['initial_capital']
        return capital, capital

    def _update_balance(self, balance: float, equity: float) -> None:
        """Persist new balance snapshot."""
        with self._get_db() as conn:
            conn.execute(
                "INSERT INTO balance_history (balance, equity) VALUES (?, ?)",
                (balance, equity)
            )

    def _log_trade(
        self, side: str, price: float, amount: float,
        pnl: float, reason: str, symbol: str,
        status: Optional[str] = None
    ) -> None:
        """Record a trade execution to the database."""
        if status is None:
            status = 'OPEN' if side == 'BUY' else 'CLOSED'

        with self._get_db() as conn:
            conn.execute(
                """INSERT INTO trades
                   (symbol, side, price, amount, cost, fee, pnl, status, reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (symbol, side, price, amount, price * amount, 0, pnl, status, reason)
            )

    def _log_signal(
        self, symbol: str, signal_type: str,
        probability: float, close_price: float
    ) -> None:
        """Record a scanner signal to the database."""
        with self._get_db() as conn:
            conn.execute(
                "INSERT INTO signals (symbol, signal_type, probability, close_price) "
                "VALUES (?, ?, ?, ?)",
                (symbol, signal_type, probability, close_price)
            )

    # ---- Portfolio Management ----

    def _load_portfolio(self) -> None:
        """Restore open positions from database on startup."""
        with self._get_db() as conn:
            rows = conn.execute(
                "SELECT symbol, amount, price FROM trades WHERE status='OPEN'"
            ).fetchall()

        for row in rows:
            sym, amt, price = row['symbol'], row['amount'], row['price']
            # SL/TP not persisted — use wide defaults until next scan recalculates
            self.portfolio[sym] = (amt, price, 0, 999999)
            logging.info(f"Restored position: {sym} ({amt:.6f} units @ {price:.2f})")

    def _is_paused(self) -> bool:
        """Check if bot is paused via status file."""
        try:
            with open("bot_status.json", "r") as f:
                return json.load(f).get("paused", False)
        except (FileNotFoundError, json.JSONDecodeError):
            return False

    # ---- Trading Logic ----

    def _scan_market(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Scan all symbols and collect ML predictions.

        Returns list of opportunities with symbol, prediction, and price.
        """
        from predict import predict_symbol

        opportunities: List[Dict[str, Any]] = []

        for symbol in symbols:
            prediction = predict_symbol(symbol)
            if not prediction:
                continue

            current_price = prediction['close']
            self._log_signal(symbol, prediction['signal'],
                             prediction['probability'], current_price)

            opportunities.append({
                "symbol": symbol,
                "prediction": prediction,
                "price": current_price
            })

        return opportunities

    def _manage_exits(
        self, opportunities: List[Dict[str, Any]],
        current_balance: float
    ) -> float:
        """
        Check all open positions for exit conditions.

        Returns updated balance after any closed positions.
        """
        commission = config['commission_rate']

        for symbol in list(self.portfolio.keys()):
            opp = next((o for o in opportunities if o['symbol'] == symbol), None)
            if not opp:
                continue

            current_price = opp['price']
            prediction = opp['prediction']
            amount, entry_price, sl_price, tp_price = self.portfolio[symbol]

            # Determine exit reason
            exit_reason: Optional[str] = None
            if sl_price > 0 and current_price <= sl_price:
                exit_reason = "SL"
            elif tp_price < 999999 and current_price >= tp_price:
                exit_reason = "TP"
            elif prediction['signal'] == "SELL":
                exit_reason = "SIGNAL_FLIP"

            if exit_reason:
                revenue = amount * current_price * (1 - commission)
                pnl = revenue - (amount * entry_price)
                current_balance += revenue
                del self.portfolio[symbol]

                self._log_trade("SELL", current_price, 0, pnl, exit_reason, symbol)
                logging.info(f"SELL {symbol} ({exit_reason}). PnL: ${pnl:.4f}")

        return current_balance

    def _manage_entries(
        self, buy_signals: List[Dict[str, Any]],
        current_balance: float, max_positions: int
    ) -> float:
        """
        Enter new positions from ranked BUY signals.

        Returns updated balance after any new entries.
        """
        open_slots = max_positions - len(self.portfolio)
        commission = config['commission_rate']

        for opp in buy_signals:
            if open_slots <= 0:
                break

            symbol = opp['symbol']
            if symbol in self.portfolio:
                continue

            prediction = opp['prediction']
            current_price = opp['price']

            # Calculate position size
            position_size = config['initial_capital'] / max_positions
            if position_size > current_balance:
                position_size = current_balance * 0.98

            if position_size < MIN_TRADE_VALUE_USDT:
                continue

            amount = position_size / current_price
            cost = amount * current_price
            fee = cost * commission

            # Adjust if insufficient balance
            if (cost + fee) > current_balance:
                amount = current_balance / (current_price * (1 + commission))
                amount *= SAFETY_MARGIN
                cost = amount * current_price
                fee = cost * commission

            if amount > 0 and cost > MIN_TRADE_VALUE_USDT:
                current_balance -= (cost + fee)
                sl, tp = self.strategy.calculate_sl_tp(
                    current_price, "BUY", prediction.get('atr', 0)
                )

                self.portfolio[symbol] = (amount, current_price, sl, tp)
                open_slots -= 1

                self._log_trade("BUY", current_price, amount, 0, "SIGNAL", symbol)
                logging.info(
                    f"BUY {symbol} @ ${current_price:.4f} "
                    f"(Conf: {prediction['probability']:.1%})"
                )

        return current_balance

    def _calculate_equity(
        self, balance: float,
        opportunities: List[Dict[str, Any]]
    ) -> float:
        """Calculate total equity = balance + unrealized position value."""
        equity_positions: float = 0.0

        for sym, (amt, entry_price, _, _) in self.portfolio.items():
            opp = next((o for o in opportunities if o['symbol'] == sym), None)
            mark_price = opp['price'] if opp else entry_price
            equity_positions += amt * mark_price

        return balance + equity_positions

    # ---- Main Loop ----

    def run(self) -> None:
        """
        Main execution loop.

        Runs indefinitely in 60-second cycles:
        Scan → Rank → Exit management → Entry management → Update equity
        """
        logging.info("="*50)
        logging.info("Bot started — Multi-Symbol Paper Trading Mode")
        logging.info(f"Symbols: {config.get('symbols', [])}")
        logging.info(f"Max positions: {config.get('max_open_positions', 3)}")
        logging.info("="*50)

        balance, equity = self._get_balance()

        # Restore any open positions from previous session
        try:
            self._load_portfolio()
        except Exception as e:
            logging.error(f"Failed to load portfolio: {e}")

        while self.running:
            # Check pause state
            if self._is_paused():
                time.sleep(PAUSE_CHECK_SECONDS)
                continue

            try:
                symbols: List[str] = config.get('symbols', [])
                max_pos: int = config.get('max_open_positions', 3)

                # Phase 1: SCAN
                logging.info(f"Scanning {len(symbols)} pairs...")
                opportunities = self._scan_market(symbols)

                # Phase 2: RANK
                buy_signals = [
                    o for o in opportunities
                    if o['prediction']['signal'] == "BUY"
                ]
                buy_signals.sort(
                    key=lambda x: x['prediction']['probability'],
                    reverse=True
                )
                logging.info(f"Found {len(buy_signals)} BUY opportunities")

                # Phase 3: EXIT management
                balance = self._manage_exits(opportunities, balance)

                # Phase 4: ENTRY management
                balance = self._manage_entries(buy_signals, balance, max_pos)

                # Phase 5: UPDATE equity
                equity = self._calculate_equity(balance, opportunities)
                self._update_balance(balance, equity)

                logging.info(
                    f"Cycle complete. Balance: ${balance:.2f} | "
                    f"Equity: ${equity:.2f} | "
                    f"Positions: {len(self.portfolio)}/{max_pos}"
                )

                time.sleep(SCAN_INTERVAL_SECONDS)

            except KeyboardInterrupt:
                logging.info("Bot stopped by user.")
                self.running = False
            except Exception as e:
                logging.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(10)


if __name__ == "__main__":
    print("\n  Starting AI Paper Trading Bot...")
    print("  Press Ctrl+C to stop.\n")
    bot = PaperTrader()
    bot.run()
