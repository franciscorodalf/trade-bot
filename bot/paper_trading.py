"""
Paper trading engine for Polymarket BTC 5-minute predictions.

Main async loop that orchestrates:
1. Real-time data collection via Binance WebSocket
2. Feature computation every 5 minutes
3. ML prediction with calibrated probabilities
4. Edge detection against Polymarket prices
5. Simulated bet placement and tracking
6. P&L calculation and persistence to SQLite
"""

import asyncio
import json
import logging
import sqlite3
import time
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any
import uuid

from data_collector import DataCollector
from features import compute_features
from predict import Predictor
from polymarket_client import PolymarketClient
from strategy import Strategy
from bet_sizing import calculate_edge

logger = logging.getLogger(__name__)

with open("config.json", "r") as f:
    config = json.load(f)

PREDICTION_INTERVAL = config["trading"]["prediction_interval_seconds"]


class PaperTrader:
    """
    Async paper trading engine for Polymarket BTC predictions.

    Lifecycle:
    1. Start data collector (WebSocket streams)
    2. Wait for sufficient data (~60 candles)
    3. Every 5 minutes:
       a. Compute features from live data
       b. Generate calibrated prediction
       c. Find BTC 5-min market on Polymarket
       d. Evaluate edge and size bet
       e. Place simulated bet
       f. Track and resolve bets
    4. Persist all state to SQLite for dashboard
    """

    def __init__(self) -> None:
        self.collector = DataCollector()
        self.predictor = Predictor()
        self.polymarket = PolymarketClient(paper_mode=True)
        self.strategy = Strategy()

        self.db_path = config["paths"]["database"]
        self.bankroll = config["trading"]["initial_capital"]
        self.peak_bankroll = self.bankroll

        # Active bets waiting for resolution
        self.pending_bets: List[Dict[str, Any]] = []

        # Stats
        self.cycles = 0
        self.total_pnl = 0.0

        self._init_database()

    # ---- Database ----

    @contextmanager
    def _get_db(self):
        """Context manager for safe database access."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_database(self) -> None:
        """Create tables for the Polymarket bot."""
        with self._get_db() as conn:
            c = conn.cursor()

            c.execute("""CREATE TABLE IF NOT EXISTS bets (
                id TEXT PRIMARY KEY,
                side TEXT,
                amount REAL,
                price REAL,
                edge REAL,
                kelly_fraction REAL,
                predicted_prob REAL,
                market_price REAL,
                expected_value REAL,
                result TEXT DEFAULT 'PENDING',
                pnl REAL DEFAULT 0,
                btc_price_at_bet REAL,
                btc_price_at_resolve REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolved_at DATETIME
            )""")

            c.execute("""CREATE TABLE IF NOT EXISTS balance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bankroll REAL,
                equity REAL,
                total_pnl REAL,
                win_rate REAL,
                total_bets INTEGER,
                open_bets INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )""")

            c.execute("""CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal TEXT,
                raw_probability REAL,
                calibrated_probability REAL,
                confidence REAL,
                features_used INTEGER,
                btc_price REAL,
                market_yes_price REAL,
                edge_up REAL,
                edge_down REAL,
                action_taken TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )""")

            # Seed balance if first run
            row = c.execute(
                "SELECT * FROM balance_history ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not row:
                c.execute(
                    "INSERT INTO balance_history (bankroll, equity, total_pnl, win_rate, total_bets, open_bets) "
                    "VALUES (?, ?, 0, 0, 0, 0)",
                    (self.bankroll, self.bankroll),
                )

    def _log_bet(self, bet: Dict[str, Any], btc_price: float) -> None:
        """Record a new bet in the database."""
        with self._get_db() as conn:
            conn.execute(
                """INSERT INTO bets
                   (id, side, amount, price, edge, kelly_fraction,
                    predicted_prob, market_price, expected_value, btc_price_at_bet)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    bet["id"], bet["side"], bet["bet_amount"],
                    bet["market_price"], bet["edge"], bet["kelly_fraction"],
                    bet["predicted_prob"], bet["market_price"],
                    bet["expected_value"], btc_price,
                ),
            )

    def _resolve_bet(self, bet_id: str, won: bool, pnl: float, btc_price: float) -> None:
        """Update bet result in database."""
        with self._get_db() as conn:
            conn.execute(
                """UPDATE bets SET result=?, pnl=?, btc_price_at_resolve=?,
                   resolved_at=CURRENT_TIMESTAMP WHERE id=?""",
                ("WIN" if won else "LOSS", pnl, btc_price, bet_id),
            )

    def _log_prediction(self, prediction: Dict, market_price: float,
                        edge_up: float, edge_down: float, action: str,
                        btc_price: float) -> None:
        """Record prediction for analysis."""
        with self._get_db() as conn:
            conn.execute(
                """INSERT INTO predictions
                   (signal, raw_probability, calibrated_probability, confidence,
                    features_used, btc_price, market_yes_price, edge_up, edge_down,
                    action_taken)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    prediction["signal"],
                    prediction["raw_probability"],
                    prediction["calibrated_probability"],
                    prediction["confidence"],
                    prediction["features_used"],
                    btc_price, market_price, edge_up, edge_down, action,
                ),
            )

    def _update_balance(self) -> None:
        """Persist current balance snapshot."""
        stats = self.strategy.get_stats()
        with self._get_db() as conn:
            conn.execute(
                """INSERT INTO balance_history
                   (bankroll, equity, total_pnl, win_rate, total_bets, open_bets)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    self.bankroll, self.bankroll, self.total_pnl,
                    stats["win_rate"], stats["total_bets"], stats["open_bets"],
                ),
            )

    # ---- Bet Resolution ----

    def _resolve_pending_bets(self, current_btc_price: float) -> None:
        """
        Resolve bets that have passed their 5-minute window.

        A bet wins if:
        - Side=UP and BTC price went up
        - Side=DOWN and BTC price went down
        """
        now = time.time()
        still_pending = []

        for bet in self.pending_bets:
            elapsed = now - bet["placed_at"]

            # Wait 5 minutes + 10s buffer for price settlement
            if elapsed < 310:
                still_pending.append(bet)
                continue

            # Resolve
            entry_price = bet["btc_price"]
            price_went_up = current_btc_price > entry_price

            won = (bet["side"] == "UP" and price_went_up) or \
                  (bet["side"] == "DOWN" and not price_went_up)

            # P&L calculation
            if won:
                pnl = bet["shares"] * 1.0 - bet["bet_amount"]
            else:
                pnl = -bet["bet_amount"]

            self.bankroll += bet["bet_amount"] + pnl
            self.total_pnl += pnl
            self.peak_bankroll = max(self.peak_bankroll, self.bankroll)

            self._resolve_bet(bet["id"], won, pnl, current_btc_price)
            self.strategy.record_result(bet["id"], won, pnl)

            result_str = "WIN" if won else "LOSS"
            logger.info(
                f"Bet {bet['id'][:8]} resolved: {result_str} "
                f"({bet['side']}) PnL: ${pnl:+.2f} | "
                f"BTC: ${entry_price:.0f} -> ${current_btc_price:.0f} | "
                f"Bankroll: ${self.bankroll:.2f}"
            )

        self.pending_bets = still_pending

    # ---- Main Loop ----

    async def run(self) -> None:
        """Main async execution loop."""
        print("\n" + "=" * 60)
        print("  Polymarket BTC Prediction Bot — Paper Trading")
        print("=" * 60)
        print(f"  Capital: ${self.bankroll:.2f} USDC")
        print(f"  Kelly fraction: {config['trading']['kelly_fraction']}")
        print(f"  Min edge: {config['trading']['min_edge']:.0%}")
        print(f"  Prediction interval: {PREDICTION_INTERVAL}s")
        print("=" * 60 + "\n")

        # Load ML model
        if not self.predictor.load():
            print("  [ERROR] Model not found. Run: python bot/train_model.py")
            return

        # Start data collection
        await self.collector.start()
        await self.polymarket.initialize()

        # Wait for data to be ready
        print("  Waiting for market data (need ~60 candles)...")
        while not self.collector.state.is_ready:
            await asyncio.sleep(5)
            candles = len(self.collector.state.candles)
            trades = len(self.collector.state.trades)
            print(f"  Collecting... Candles: {candles}/60 | Trades: {trades}", end="\r")

        print("\n  Data ready. Starting prediction loop.\n")

        try:
            while True:
                await self._cycle()
                await asyncio.sleep(PREDICTION_INTERVAL)
        except KeyboardInterrupt:
            print("\n\n  Bot stopped by user.")
        finally:
            await self.collector.stop()
            self._print_summary()

    async def _cycle(self) -> None:
        """Single prediction-bet cycle."""
        self.cycles += 1
        state = self.collector.get_state()

        candles = list(state.candles)
        if not candles:
            return
        btc_price = candles[-1].close

        # Resolve any pending bets
        self._resolve_pending_bets(btc_price)

        # Compute features
        features = compute_features(state)
        if features is None:
            logger.warning("Feature computation failed. Skipping cycle.")
            return

        # Generate prediction
        prediction = self.predictor.predict(features)
        if prediction is None:
            logger.warning("Prediction failed. Skipping cycle.")
            return

        # Get Polymarket market price
        market_yes_price = await self._get_market_price()

        # Calculate edges
        edge_up = calculate_edge(prediction["calibrated_probability"], market_yes_price)
        edge_down = calculate_edge(1 - prediction["calibrated_probability"], 1 - market_yes_price)

        # Strategy evaluation
        bet_decision = self.strategy.evaluate(prediction, market_yes_price, self.bankroll)

        action = "BET" if bet_decision else "SKIP"
        self._log_prediction(
            prediction, market_yes_price, edge_up, edge_down, action, btc_price
        )

        if bet_decision:
            bet_id = str(uuid.uuid4())[:12]
            bet_decision["id"] = bet_id
            bet_decision["btc_price"] = btc_price
            bet_decision["placed_at"] = time.time()
            bet_decision["shares"] = bet_decision["bet_amount"] / bet_decision["market_price"]

            self.bankroll -= bet_decision["bet_amount"]

            self.pending_bets.append(bet_decision)
            self.strategy.add_open_bet(bet_decision)
            self._log_bet(bet_decision, btc_price)

            print(
                f"  [{datetime.now().strftime('%H:%M:%S')}] "
                f"BET {bet_decision['side']} ${bet_decision['bet_amount']:.2f} | "
                f"Edge: {bet_decision['edge']:.1%} | "
                f"BTC: ${btc_price:,.0f} | "
                f"Bankroll: ${self.bankroll:.2f}"
            )
        else:
            print(
                f"  [{datetime.now().strftime('%H:%M:%S')}] "
                f"SKIP | {prediction['signal']} ({prediction['calibrated_probability']:.1%}) | "
                f"Edge UP={edge_up:+.1%} DOWN={edge_down:+.1%} | "
                f"BTC: ${btc_price:,.0f} | "
                f"Bankroll: ${self.bankroll:.2f}"
            )

        self._update_balance()

    async def _get_market_price(self) -> float:
        """Get current Polymarket YES price for BTC 5-min UP market."""
        if self.polymarket.paper_mode:
            return 0.50

        markets = await self.polymarket.find_btc_5min_markets()
        if markets:
            market = markets[0]
            price = await self.polymarket.get_market_price(market["yes_token_id"])
            if price is not None:
                return price

        return 0.50

    def _print_summary(self) -> None:
        """Print final trading session summary."""
        stats = self.strategy.get_stats()
        drawdown = (self.peak_bankroll - self.bankroll) / self.peak_bankroll if self.peak_bankroll > 0 else 0

        print("\n" + "=" * 60)
        print("  SESSION SUMMARY")
        print("=" * 60)
        print(f"  Cycles:          {self.cycles}")
        print(f"  Total bets:      {stats['total_bets']}")
        print(f"  Wins:            {stats['total_wins']}")
        print(f"  Win rate:        {stats['win_rate']:.1%}")
        print(f"  Total P&L:       ${self.total_pnl:+.2f}")
        print(f"  Final bankroll:  ${self.bankroll:.2f}")
        print(f"  Peak bankroll:   ${self.peak_bankroll:.2f}")
        print(f"  Max drawdown:    {drawdown:.1%}")
        print(f"  Pending bets:    {len(self.pending_bets)}")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(config["paths"]["logs"]),
        ],
    )

    print("\n  Starting Polymarket BTC Prediction Bot...")
    print("  Press Ctrl+C to stop.\n")

    bot = PaperTrader()
    asyncio.run(bot.run())
