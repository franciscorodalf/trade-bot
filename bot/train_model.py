"""
ML model training pipeline.

Trains a Universal Random Forest Classifier on combined historical data
from all configured cryptocurrency pairs. The universal approach learns
general market patterns rather than symbol-specific behaviors.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
import joblib
import json
import logging
import os
from typing import List

from utils import fetch_data, add_indicators, FEATURE_COLUMNS

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

logging.basicConfig(
    filename=config['paths']['logs'],
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


def train() -> None:
    """
    Train a universal Random Forest model on multi-symbol historical data.

    Steps:
    1. Fetch ~5000 candles per configured symbol from Binance
    2. Compute 24 technical features for each dataset
    3. Combine all data into a single training set
    4. Train/test split (80/20) and fit RandomForest
    5. Evaluate and save model to disk

    The trained model is saved to the path specified in config.json.
    """
    all_data: List[pd.DataFrame] = []
    symbols: List[str] = config.get('symbols', [config.get('symbol')])

    print(f"\n{'='*50}")
    print(f"  Training Universal Model on {len(symbols)} pairs")
    print(f"{'='*50}\n")

    for i, symbol in enumerate(symbols, 1):
        print(f"  [{i}/{len(symbols)}] Fetching {symbol}...")
        df = fetch_data(symbol=symbol, limit=5000)

        if df is None:
            print(f"  [!] Failed to fetch data for {symbol}. Skipping.")
            continue

        df = add_indicators(df)
        if df is not None and not df.empty:
            all_data.append(df)
            print(f"  [+] {symbol}: {len(df)} data points ready")
        else:
            print(f"  [!] {symbol}: Not enough data for indicators")

    if not all_data:
        print("\n  [ERROR] No data available for training.")
        return

    # Combine all symbol data into one dataset
    full_df = pd.concat(all_data, ignore_index=True)
    print(f"\n  Total combined data points: {len(full_df):,}")

    # Use shared feature columns from utils
    features = FEATURE_COLUMNS
    X = full_df[features]
    y = full_df['target']

    # Train/test split
    # Note: Random split is used here intentionally — the universal model
    # learns general patterns across all symbols and timeframes, not
    # sequential dependencies within a single time series.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=True, random_state=42
    )

    # Initialize model from config hyperparameters
    params = config['model_params']
    model = RandomForestClassifier(
        n_estimators=params['n_estimators'],
        max_depth=params['max_depth'],
        min_samples_leaf=params['min_samples_leaf'],
        random_state=params['random_state'],
        n_jobs=-1  # Use all CPU cores
    )

    print(f"\n  Training RandomForest (n_estimators={params['n_estimators']})...")
    model.fit(X_train, y_train)

    # Evaluate on held-out test set
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    cm = confusion_matrix(y_test, y_pred)

    print(f"\n{'='*50}")
    print(f"  Model Accuracy: {accuracy:.4f}")
    print(f"{'='*50}")
    print(f"\n  Confusion Matrix:")
    print(f"  {cm}")
    print(f"\n  Classification Report:")
    print(classification_report(y_test, y_pred, target_names=['DOWN', 'UP']))

    # Feature importance (top 5)
    importances = pd.Series(
        model.feature_importances_, index=features
    ).sort_values(ascending=False)
    print("  Top 5 Features:")
    for feat, imp in importances.head(5).items():
        print(f"    {feat}: {imp:.4f}")

    # Save model
    model_path = config['paths']['model']
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump(model, model_path)

    print(f"\n  Model saved to: {model_path}")
    print(f"{'='*50}\n")

    logging.info(
        f"Universal Model trained on {len(symbols)} pairs. "
        f"Accuracy: {accuracy:.4f}. Data points: {len(full_df)}"
    )


if __name__ == "__main__":
    train()
