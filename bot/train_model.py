"""
XGBoost model training pipeline with walk-forward validation.

Trains a calibrated XGBoost classifier for binary BTC price prediction
(UP/DOWN in 5-minute windows) using proper time-series validation.
"""

import json
import logging
import os
import time
from typing import Dict, List, Tuple, Optional, Any

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    brier_score_loss,
    log_loss,
    accuracy_score,
    classification_report,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

from features import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

# Load config
with open("config.json", "r") as f:
    config = json.load(f)


def fetch_training_data(days: int = 30) -> Optional[pd.DataFrame]:
    """
    Fetch historical 1-minute BTC/USDT candles from Binance
    and compute all features + target labels.

    Args:
        days: Number of days of history to fetch.

    Returns:
        DataFrame with features and 'target' column (1=UP, 0=DOWN in next 5 min).
    """
    import ccxt

    exchange = ccxt.binance({
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
    })

    symbol = config["binance"]["ccxt_symbol"]
    timeframe = "1m"
    limit = 1500  # Max per request
    total_candles = days * 24 * 60
    all_candles = []

    print(f"\n  Fetching {total_candles:,} candles ({days} days) of {symbol} 1m data...")

    # Fetch in batches going backwards
    end_time = int(time.time() * 1000)
    fetched = 0

    while fetched < total_candles:
        try:
            since = end_time - (limit * 60 * 1000)
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            if not ohlcv:
                break
            all_candles.extend(ohlcv)
            end_time = ohlcv[0][0] - 1
            fetched += len(ohlcv)
            print(f"  Fetched {fetched:,}/{total_candles:,} candles...", end="\r")
            time.sleep(0.5)  # Rate limit
        except Exception as e:
            logger.warning(f"Fetch error: {e}. Retrying...")
            time.sleep(2)

    if not all_candles:
        print("  [ERROR] No data fetched.")
        return None

    # Sort chronologically and deduplicate
    all_candles.sort(key=lambda x: x[0])
    seen = set()
    unique = []
    for c in all_candles:
        if c[0] not in seen:
            seen.add(c[0])
            unique.append(c)

    df = pd.DataFrame(unique, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)

    print(f"\n  Total unique candles: {len(df):,}")
    print(f"  Date range: {df.index[0]} → {df.index[-1]}")

    # Compute features
    df = _compute_offline_features(df)

    # Create 5-minute forward target
    # Target: will price be higher 5 candles (minutes) from now?
    df["target"] = (df["close"].shift(-5) > df["close"]).astype(int)

    # Drop NaN rows
    df = df.dropna()

    print(f"  Samples after feature computation: {len(df):,}")
    print(f"  Class balance: UP={df['target'].mean():.1%} / DOWN={1 - df['target'].mean():.1%}")

    return df


def _compute_offline_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all features on historical OHLCV DataFrame."""
    import ta

    df = df.copy()

    # Price returns
    df["return_1m"] = df["close"].pct_change()
    df["return_5m"] = df["close"].pct_change(5)
    df["return_15m"] = df["close"].pct_change(15)
    df["return_30m"] = df["close"].pct_change(30)
    df["log_return_1m"] = np.log(df["close"] / df["close"].shift(1))
    df["log_return_5m"] = np.log(df["close"] / df["close"].shift(5))

    # Volatility
    df["volatility_5m"] = df["return_1m"].rolling(5).std()
    df["volatility_15m"] = df["return_1m"].rolling(15).std()

    # RSI
    df["rsi_14"] = ta.momentum.rsi(df["close"], window=14)
    df["rsi_7"] = ta.momentum.rsi(df["close"], window=7)

    # MACD (normalized by price in bps)
    macd = ta.trend.macd_diff(df["close"], window_slow=26, window_fast=12, window_sign=9)
    df["macd"] = macd / df["close"] * 10000
    macd_line = ta.trend.macd(df["close"], window_slow=26, window_fast=12)
    macd_signal = ta.trend.macd_signal(df["close"], window_slow=26, window_fast=12, window_sign=9)
    df["macd_signal"] = macd_signal / df["close"] * 10000
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # Price vs SMA
    sma_20 = ta.trend.sma_indicator(df["close"], window=20)
    df["price_vs_sma_20"] = (df["close"] - sma_20) / sma_20 * 10000

    # Bollinger Bands
    bb_high = ta.volatility.bollinger_hband(df["close"], window=20, window_dev=2)
    bb_low = ta.volatility.bollinger_lband(df["close"], window=20, window_dev=2)
    bb_range = bb_high - bb_low
    df["bb_position"] = (df["close"] - bb_low) / bb_range.replace(0, np.nan)
    df["bb_width"] = ta.volatility.bollinger_wband(df["close"], window=20, window_dev=2) * 10000

    # ATR
    atr = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=14)
    df["atr_14"] = atr.average_true_range()
    df["atr_ratio"] = df["atr_14"] / df["close"] * 10000

    # Simulated order book features (use volume proxies for historical)
    df["spread_bps"] = (df["high"] - df["low"]) / df["close"] * 10000
    df["spread_change"] = df["spread_bps"].pct_change()
    df["book_imbalance_5"] = 0  # Not available in historical OHLCV
    df["book_imbalance_10"] = 0
    df["book_imbalance_20"] = 0
    df["bid_depth_usd"] = 0
    df["ask_depth_usd"] = 0
    df["depth_ratio"] = 1

    # Volume-based trade flow proxies
    # Use up/down candle volume as proxy for buy/sell pressure
    up_candle = (df["close"] > df["open"]).astype(float)
    df["buy_sell_ratio_1m"] = up_candle.rolling(1).mean() * 2
    df["buy_sell_ratio_5m"] = up_candle.rolling(5).mean() * 2
    df["cvd_1m"] = (up_candle * 2 - 1) * df["volume"]
    df["cvd_1m"] = df["cvd_1m"] / (df["volume"].rolling(20).mean() + 1e-10)
    df["cvd_5m"] = df["cvd_1m"].rolling(5).sum()
    df["trade_intensity_1m"] = df["volume"] / (df["volume"].rolling(60).mean() + 1e-10)
    df["trade_intensity_5m"] = df["volume"].rolling(5).mean() / (df["volume"].rolling(60).mean() + 1e-10)
    df["large_trade_ratio"] = 0  # Not available in historical OHLCV

    # Volume features
    df["volume_ratio_5m"] = df["volume"].rolling(5).mean() / (df["volume"].rolling(20).mean() + 1e-10)
    df["volume_ratio_15m"] = df["volume"].rolling(15).mean() / (df["volume"].rolling(60).mean() + 1e-10)
    vol_5 = df["volume"].rolling(5).mean()
    vol_prev_5 = df["volume"].shift(5).rolling(5).mean()
    df["volume_momentum"] = (vol_5 - vol_prev_5) / (vol_prev_5 + 1e-10)

    # Derivatives (not available in historical OHLCV — set to 0)
    df["funding_rate"] = 0
    df["funding_rate_abs"] = 0
    df["open_interest_change"] = 0

    # Sentiment (not available in historical — set to neutral)
    df["fear_greed_normalized"] = 0

    return df


def walk_forward_train(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Train model using sliding window walk-forward validation.

    Each fold:
    1. Train on [i : i + train_window]
    2. Skip purge_gap (prevent leakage from 5-min target)
    3. Test on [i + train_window + purge_gap : i + train_window + purge_gap + test_window]

    Returns:
        Dict with trained model, scaler, calibrator, and metrics.
    """
    wf_config = config["model"]["walk_forward"]
    model_params = config["model"]["params"]

    train_minutes = wf_config["train_days"] * 24 * 60
    test_minutes = wf_config["test_days"] * 24 * 60
    purge_minutes = wf_config["purge_gap_hours"] * 60
    step = test_minutes  # Non-overlapping test windows

    X = df[FEATURE_COLUMNS].values
    y = df["target"].values

    fold_metrics: List[Dict[str, float]] = []
    all_probs: List[np.ndarray] = []
    all_labels: List[np.ndarray] = []

    n_folds = max(1, (len(df) - train_minutes - purge_minutes - test_minutes) // step + 1)
    n_folds = min(n_folds, 20)  # Cap at 20 folds

    print(f"\n  Walk-Forward Validation:")
    print(f"  Train window: {wf_config['train_days']}d | Test: {wf_config['test_days']}d | Purge: {wf_config['purge_gap_hours']}h")
    print(f"  Total folds: {n_folds}")
    print(f"  {'─' * 60}")

    for fold in range(n_folds):
        train_start = fold * step
        train_end = train_start + train_minutes
        test_start = train_end + purge_minutes
        test_end = test_start + test_minutes

        if test_end > len(X):
            break

        X_train = X[train_start:train_end]
        y_train = y[train_start:train_end]
        X_test = X[test_start:test_end]
        y_test = y[test_start:test_end]

        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # Train XGBoost
        model = xgb.XGBClassifier(
            n_estimators=model_params["n_estimators"],
            max_depth=model_params["max_depth"],
            learning_rate=model_params["learning_rate"],
            subsample=model_params["subsample"],
            colsample_bytree=model_params["colsample_bytree"],
            min_child_weight=model_params["min_child_weight"],
            reg_alpha=model_params["reg_alpha"],
            reg_lambda=model_params["reg_lambda"],
            random_state=model_params["random_state"],
            eval_metric=model_params["eval_metric"],
            use_label_encoder=False,
            verbosity=0,
        )

        # Train with early stopping
        model.fit(
            X_train_scaled, y_train,
            eval_set=[(X_test_scaled, y_test)],
            verbose=False,
        )

        # Predict probabilities
        probs = model.predict_proba(X_test_scaled)[:, 1]
        preds = (probs >= 0.5).astype(int)

        # Metrics
        acc = accuracy_score(y_test, preds)
        brier = brier_score_loss(y_test, probs)
        ll = log_loss(y_test, probs)
        auc = roc_auc_score(y_test, probs) if len(np.unique(y_test)) > 1 else 0.5

        fold_metrics.append({"accuracy": acc, "brier": brier, "log_loss": ll, "auc": auc})
        all_probs.append(probs)
        all_labels.append(y_test)

        print(
            f"  Fold {fold + 1:2d}/{n_folds}: "
            f"Acc={acc:.3f} | Brier={brier:.4f} | "
            f"LogLoss={ll:.4f} | AUC={auc:.3f}"
        )

    # Aggregate metrics
    avg_metrics = {
        k: np.mean([m[k] for m in fold_metrics]) for k in fold_metrics[0]
    }

    print(f"  {'─' * 60}")
    print(f"  AVERAGE: Acc={avg_metrics['accuracy']:.3f} | "
          f"Brier={avg_metrics['brier']:.4f} | AUC={avg_metrics['auc']:.3f}")

    # Final model: train on all data
    print(f"\n  Training final model on all {len(X):,} samples...")
    final_scaler = StandardScaler()
    X_scaled = final_scaler.fit_transform(X)

    final_model = xgb.XGBClassifier(
        n_estimators=model_params["n_estimators"],
        max_depth=model_params["max_depth"],
        learning_rate=model_params["learning_rate"],
        subsample=model_params["subsample"],
        colsample_bytree=model_params["colsample_bytree"],
        min_child_weight=model_params["min_child_weight"],
        reg_alpha=model_params["reg_alpha"],
        reg_lambda=model_params["reg_lambda"],
        random_state=model_params["random_state"],
        eval_metric=model_params["eval_metric"],
        use_label_encoder=False,
        verbosity=0,
    )
    final_model.fit(X_scaled, y, verbose=False)

    # Calibrate probabilities using isotonic regression
    print("  Calibrating probabilities (isotonic regression)...")
    all_probs_flat = np.concatenate(all_probs)
    all_labels_flat = np.concatenate(all_labels)
    calibrator = _fit_isotonic_calibrator(all_probs_flat, all_labels_flat)

    # Feature importance
    importances = pd.Series(
        final_model.feature_importances_, index=FEATURE_COLUMNS
    ).sort_values(ascending=False)

    print(f"\n  Top 10 Features:")
    for feat, imp in importances.head(10).items():
        print(f"    {feat}: {imp:.4f}")

    return {
        "model": final_model,
        "scaler": final_scaler,
        "calibrator": calibrator,
        "metrics": avg_metrics,
        "fold_metrics": fold_metrics,
        "feature_importance": importances.to_dict(),
    }


def _fit_isotonic_calibrator(probs: np.ndarray, labels: np.ndarray):
    """Fit an isotonic regression calibrator on out-of-fold predictions."""
    from sklearn.isotonic import IsotonicRegression

    calibrator = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds="clip")
    calibrator.fit(probs, labels)
    return calibrator


def save_model(result: Dict[str, Any]) -> None:
    """Save trained model, scaler, and calibrator to disk."""
    paths = config["paths"]

    os.makedirs(os.path.dirname(paths["model"]), exist_ok=True)
    joblib.dump(result["model"], paths["model"])
    joblib.dump(result["scaler"], paths["scaler"])
    joblib.dump(result["calibrator"], paths["calibrator"])

    # Save metrics
    metrics_path = paths.get("backtest_results", "logs/train_metrics.json")
    os.makedirs(os.path.dirname(metrics_path), exist_ok=True)
    with open(metrics_path, "w") as f:
        json.dump({
            "metrics": result["metrics"],
            "fold_metrics": result["fold_metrics"],
            "feature_importance": result["feature_importance"],
        }, f, indent=2, default=str)

    print(f"\n  Model saved to: {paths['model']}")
    print(f"  Scaler saved to: {paths['scaler']}")
    print(f"  Calibrator saved to: {paths['calibrator']}")
    print(f"  Metrics saved to: {metrics_path}")


def train(days: int = 30) -> None:
    """Full training pipeline: fetch data → train → validate → save."""
    print(f"\n{'=' * 60}")
    print("  Polymarket BTC Prediction Model — Training Pipeline")
    print(f"{'=' * 60}")

    # Step 1: Fetch data
    df = fetch_training_data(days=days)
    if df is None or len(df) < 1000:
        print("  [ERROR] Insufficient training data.")
        return

    # Step 2: Walk-forward train + validate
    result = walk_forward_train(df)

    # Step 3: Evaluate quality
    metrics = result["metrics"]
    print(f"\n{'=' * 60}")
    if metrics["auc"] > 0.52:
        print(f"  Model shows signal (AUC={metrics['auc']:.3f} > 0.52)")
        print("  Saving model...")
        save_model(result)
    else:
        print(f"  WARNING: Model shows weak signal (AUC={metrics['auc']:.3f})")
        print("  Saving anyway — consider tuning features or parameters.")
        save_model(result)

    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    train(days=30)
