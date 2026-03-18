"""
Walk-forward backtesting engine for the Polymarket BTC prediction bot.

Simulates the full prediction -> edge detection -> bet sizing -> P&L pipeline
on historical data to evaluate strategy performance before live trading.
"""

import json
import logging
import os
from typing import Dict, List, Any

import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

from features import FEATURE_COLUMNS
from bet_sizing import size_bet, calculate_edge

logger = logging.getLogger(__name__)

with open("config.json", "r") as f:
    config = json.load(f)


class Backtester:
    """
    Simulates the bot's strategy on historical data.

    Measures:
    - Model quality: Brier score, log loss, AUC, calibration
    - Strategy performance: P&L, Sharpe, max drawdown, win rate
    """

    def __init__(self, market_price: float = 0.50) -> None:
        self.market_price = market_price
        self.min_edge = config["trading"]["min_edge"]
        self.kelly_fraction = config["trading"]["kelly_fraction"]
        self.initial_capital = config["trading"]["initial_capital"]
        self.min_bet = config["trading"]["min_bet"]
        self.max_bet = config["trading"]["max_bet"]

    def run(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Run full backtest on prepared DataFrame.

        Args:
            df: DataFrame with FEATURE_COLUMNS + 'target' column.

        Returns:
            Dict with model metrics, strategy metrics, and calibration.
        """
        print(f"\n{'=' * 60}")
        print("  BACKTESTING ENGINE")
        print(f"{'=' * 60}")
        print(f"  Samples: {len(df):,}")
        print(f"  Market price: {self.market_price}")
        print(f"  Min edge: {self.min_edge:.0%}")
        print(f"  Kelly fraction: {self.kelly_fraction}")
        print(f"  Initial capital: ${self.initial_capital}")

        model = joblib.load(config["paths"]["model"])
        scaler = joblib.load(config["paths"]["scaler"])
        calibrator = joblib.load(config["paths"]["calibrator"])

        X = df[FEATURE_COLUMNS].values
        y = df["target"].values

        X_scaled = scaler.transform(X)
        raw_probs = model.predict_proba(X_scaled)[:, 1]
        cal_probs = calibrator.predict(raw_probs)
        cal_probs = np.clip(cal_probs, 0.01, 0.99)

        model_metrics = self._evaluate_model(y, raw_probs, cal_probs)
        strategy_results = self._simulate_strategy(y, cal_probs)
        calibration = self._calibration_analysis(y, cal_probs)

        results = {
            "model_metrics": model_metrics,
            "strategy": strategy_results,
            "calibration": calibration,
        }

        self._print_report(results)
        return results

    def _evaluate_model(self, y, raw_probs, cal_probs):
        preds = (cal_probs >= 0.5).astype(int)
        return {
            "accuracy": float(np.mean(preds == y)),
            "brier_score": float(brier_score_loss(y, cal_probs)),
            "brier_score_raw": float(brier_score_loss(y, raw_probs)),
            "log_loss": float(log_loss(y, cal_probs)),
            "log_loss_raw": float(log_loss(y, raw_probs)),
            "auc": float(roc_auc_score(y, cal_probs)),
            "auc_raw": float(roc_auc_score(y, raw_probs)),
            "mean_predicted_prob": float(np.mean(cal_probs)),
            "mean_actual_prob": float(np.mean(y)),
        }

    def _simulate_strategy(self, y, cal_probs):
        bankroll = self.initial_capital
        trades: List[Dict[str, Any]] = []

        for i in range(0, len(y), 5):
            if i >= len(y):
                break

            prob_up = cal_probs[i]
            actual_up = y[i]

            edge_up = calculate_edge(prob_up, self.market_price)
            edge_down = calculate_edge(1 - prob_up, 1 - self.market_price)

            if edge_up > edge_down and edge_up >= self.min_edge:
                bet = size_bet(prob_up, self.market_price, bankroll, "UP")
            elif edge_down > edge_up and edge_down >= self.min_edge:
                bet = size_bet(prob_up, self.market_price, bankroll, "DOWN")
            else:
                continue

            if bet is None or bankroll < self.min_bet:
                continue

            amount = bet["bet_amount"]
            side = bet["side"]
            price = bet["market_price"]

            won = (side == "UP" and actual_up == 1) or \
                  (side == "DOWN" and actual_up == 0)

            if won:
                pnl = (amount / price) * 1.0 - amount
            else:
                pnl = -amount

            bankroll += pnl

            trades.append({
                "side": side, "amount": amount, "edge": bet["edge"],
                "won": won, "pnl": pnl, "bankroll": bankroll,
            })

            if bankroll < self.min_bet:
                break

        if not trades:
            return {"total_trades": 0, "message": "No trades taken (edge too low)"}

        wins = sum(1 for t in trades if t["won"])
        pnls = [t["pnl"] for t in trades]
        bankrolls = [t["bankroll"] for t in trades]

        returns = np.array(pnls) / self.initial_capital
        intervals_per_year = 365.25 * 24 * 12
        sharpe = (np.mean(returns) / (np.std(returns) + 1e-10)) * np.sqrt(intervals_per_year)

        peak_arr = np.maximum.accumulate(bankrolls)
        drawdowns = (peak_arr - bankrolls) / (peak_arr + 1e-10)
        max_dd = float(np.max(drawdowns))

        neg_pnl_sum = abs(sum(p for p in pnls if p < 0))

        return {
            "total_trades": len(trades),
            "wins": wins,
            "losses": len(trades) - wins,
            "win_rate": wins / len(trades),
            "total_pnl": sum(pnls),
            "avg_pnl": float(np.mean(pnls)),
            "avg_win": float(np.mean([p for p in pnls if p > 0])) if wins > 0 else 0,
            "avg_loss": float(np.mean([p for p in pnls if p <= 0])) if (len(trades) - wins) > 0 else 0,
            "sharpe_ratio": float(sharpe),
            "max_drawdown": max_dd,
            "final_bankroll": bankroll,
            "return_pct": (bankroll - self.initial_capital) / self.initial_capital,
            "profit_factor": sum(p for p in pnls if p > 0) / neg_pnl_sum if neg_pnl_sum > 0 else float("inf"),
        }

    def _calibration_analysis(self, y, cal_probs, n_bins=10):
        bins = np.linspace(0, 1, n_bins + 1)
        bin_centers, bin_actuals, bin_counts = [], [], []

        for i in range(n_bins):
            mask = (cal_probs >= bins[i]) & (cal_probs < bins[i + 1])
            if mask.sum() > 0:
                bin_centers.append(float(np.mean(cal_probs[mask])))
                bin_actuals.append(float(np.mean(y[mask])))
                bin_counts.append(int(mask.sum()))

        total = sum(bin_counts)
        ece = sum(
            (c / total) * abs(a - ce)
            for ce, a, c in zip(bin_centers, bin_actuals, bin_counts)
        )

        return {"ece": float(ece), "bin_centers": bin_centers,
                "bin_actuals": bin_actuals, "bin_counts": bin_counts}

    def _print_report(self, results):
        mm = results["model_metrics"]
        st = results["strategy"]
        cal = results["calibration"]

        print(f"\n{'─' * 60}")
        print("  MODEL METRICS")
        print(f"{'─' * 60}")
        print(f"  Accuracy:     {mm['accuracy']:.3f}")
        print(f"  Brier Score:  {mm['brier_score']:.4f} (raw: {mm['brier_score_raw']:.4f})")
        print(f"  Log Loss:     {mm['log_loss']:.4f} (raw: {mm['log_loss_raw']:.4f})")
        print(f"  AUC:          {mm['auc']:.3f} (raw: {mm['auc_raw']:.3f})")
        print(f"  ECE:          {cal['ece']:.4f}")

        if st.get("total_trades", 0) > 0:
            print(f"\n{'─' * 60}")
            print("  STRATEGY PERFORMANCE")
            print(f"{'─' * 60}")
            print(f"  Total trades:    {st['total_trades']}")
            print(f"  Win rate:        {st['win_rate']:.1%}")
            print(f"  Total P&L:       ${st['total_pnl']:+.2f}")
            print(f"  Profit factor:   {st['profit_factor']:.2f}")
            print(f"  Sharpe ratio:    {st['sharpe_ratio']:.2f}")
            print(f"  Max drawdown:    {st['max_drawdown']:.1%}")
            print(f"  Final bankroll:  ${st['final_bankroll']:.2f}")
            print(f"  Return:          {st['return_pct']:+.1%}")

        print(f"\n{'─' * 60}")
        print("  CALIBRATION (predicted vs actual)")
        print(f"{'─' * 60}")
        for ce, a, c in zip(cal["bin_centers"], cal["bin_actuals"], cal["bin_counts"]):
            bar = "#" * int(c / max(cal["bin_counts"]) * 30)
            print(f"  {ce:.2f} -> {a:.2f} ({c:5d}) {bar}")

        print(f"{'=' * 60}\n")


def run_backtest(days: int = 30):
    from train_model import fetch_training_data

    print("  Fetching historical data for backtest...")
    df = fetch_training_data(days=days)
    if df is None or len(df) < 100:
        print("  [ERROR] Insufficient data for backtest.")
        return {}

    bt = Backtester(market_price=0.50)
    results = bt.run(df)

    results_path = config["paths"]["backtest_results"]
    os.makedirs(os.path.dirname(results_path), exist_ok=True)

    def convert(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=convert)

    print(f"  Results saved to: {results_path}")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_backtest(days=14)
