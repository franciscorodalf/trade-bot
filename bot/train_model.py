import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
import joblib
import json
import logging
import os
import asyncio
from utils import fetch_data, add_indicators

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

logging.basicConfig(filename=config['paths']['logs'], level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

async def train():
    all_data = []
    symbols = config.get('symbols', [config.get('symbol')])
    
    print(f"Training on symbols: {symbols}")
    
    # Async Parallel Fetching
    print("Fetching data for all symbols (Async)...")
    tasks = [fetch_data(symbol=sym, limit=5000) for sym in symbols]
    results = await asyncio.gather(*tasks)
    
    print("Processing fetched data...")
    for i, df in enumerate(results):
        symbol = symbols[i]
        
        if df is None:
            print(f"Failed to fetch data for {symbol}.")
            continue
            
        print(f"Adding indicators for {symbol}...")
        df = add_indicators(df)
        
        if df is not None and not df.empty:
            all_data.append(df)
    
    if not all_data:
        print("No data available for training.")
        return

    # Combine all dataframes
    full_df = pd.concat(all_data)
    print(f"Total Combined Data Points: {len(full_df)}")
    
    # Define features and target
    features = [
        'return', 'sma_20', 'sma_50', 'ema_12', 'rsi', 'volatility', 'atr',
        'macd', 'bb_width',
        'return_lag_1', 'return_lag_2', 'return_lag_3',
        'rsi_lag_1', 'rsi_lag_2', 'rsi_lag_3',
        'volatility_lag_1', 'volatility_lag_2', 'volatility_lag_3',
        'macd_lag_1', 'macd_lag_2', 'macd_lag_3',
        'bb_width_lag_1', 'bb_width_lag_2', 'bb_width_lag_3',
        # Multi-Timeframe Features (1h)
        'rsi_1h', 'macd_1h', 'sma_20_1h', 'sma_50_1h',
        # Multi-Timeframe Features (4h)
        'rsi_4h', 'macd_4h', 'sma_20_4h', 'sma_50_4h'
    ]
    
    X = full_df[features]
    y = full_df['target']
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=True, random_state=42)
    
    # Initialize model with config params
    params = config['model_params']
    model = RandomForestClassifier(
        n_estimators=params['n_estimators'],
        max_depth=params['max_depth'],
        min_samples_leaf=params['min_samples_leaf'],
        random_state=params['random_state']
    )
    
    print("Training Universal Model...")
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    cm = confusion_matrix(y_test, y_pred)
    
    print(f"Model Accuracy: {acc:.4f}")
    print("Confusion Matrix:")
    print(cm)
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    # Save model
    model_path = config['paths']['model']
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump(model, model_path)
    print(f"Universal Model saved to {model_path}")
    
    logging.info(f"Universal Model trained on {len(symbols)} pairs. Accuracy: {acc:.4f}")

if __name__ == "__main__":
    asyncio.run(train())
