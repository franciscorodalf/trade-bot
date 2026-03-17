"""
Real-time prediction engine.

Loads the trained Random Forest model and generates BUY/SELL/HOLD signals
for any given trading pair, with volatility filtering.
"""

import joblib
import pandas as pd
import json
import logging
import os
from typing import Optional, Dict, Any

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

logging.basicConfig(
    filename=config['paths']['logs'],
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


def load_model():
    """
    Load the trained ML model from disk.

    Returns:
        Trained sklearn model, or None if file doesn't exist.
    """
    model_path = config['paths']['model']
    if not os.path.exists(model_path):
        logging.error("Model file not found. Run 'python bot/train_model.py' first.")
        return None
    return joblib.load(model_path)


def predict(symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Backward-compatible alias for predict_symbol."""
    return predict_symbol(symbol)


def predict_symbol(symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Generate a trading signal for a specific symbol.

    Pipeline:
    1. Load trained model
    2. Fetch latest 100 candles + compute indicators
    3. Apply volatility filter (skip flat markets)
    4. Run ML inference → probability of price going up
    5. Map probability to signal (BUY/SELL/HOLD) via thresholds

    Args:
        symbol: Trading pair (e.g. 'BTC/USDT'). Defaults to config.

    Returns:
        Dict with keys: signal, probability, volatility, atr, close, reason.
        None if data fetching or model loading fails.
    """
    model = load_model()
    if model is None:
        return None

    from utils import fetch_data, add_indicators, FEATURE_COLUMNS

    # Fetch recent data for the target symbol
    df = fetch_data(symbol=symbol, limit=100)
    if df is not None:
        df = add_indicators(df)

    if df is None or df.empty:
        logging.error(f"No data available for prediction on {symbol}.")
        return None

    # Use the most recent completed candle
    last_row = df.iloc[-1]

    # Volatility filter: skip flat/dead markets
    volatility: float = last_row['volatility']
    vol_threshold: float = config['volatility_threshold']

    if volatility < vol_threshold:
        logging.info(
            f"[{symbol}] Low volatility ({volatility:.4f} < {vol_threshold}). Skipping."
        )
        return {
            "signal": "HOLD",
            "probability": 0.0,
            "volatility": volatility,
            "close": last_row['close'],
            "reason": "Low Volatility"
        }

    # Prepare feature vector
    features = FEATURE_COLUMNS
    X_new = pd.DataFrame([last_row[features]])

    # ML inference: probability of next candle going up
    prob: float = model.predict_proba(X_new)[0][1]

    # Map probability to signal via thresholds
    buy_threshold: float = config['buy_threshold']
    sell_threshold: float = config['sell_threshold']

    signal = "HOLD"
    if prob > buy_threshold:
        signal = "BUY"
    elif prob < sell_threshold:
        signal = "SELL"

    logging.info(
        f"[{symbol}] Prediction: {signal} "
        f"(Prob: {prob:.4f}, Close: {last_row['close']:.8f})"
    )

    return {
        "signal": signal,
        "probability": prob,
        "volatility": volatility,
        "atr": last_row['atr'],
        "close": last_row['close'],
        "reason": "Model Signal"
    }


if __name__ == "__main__":
    result = predict()
    if result:
        print(f"Signal: {result['signal']} | Prob: {result['probability']:.4f}")
    else:
        print("Prediction failed. Check logs.")
