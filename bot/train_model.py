import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
import joblib
import json
import logging
import os
from utils import fetch_data, add_indicators

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

logging.basicConfig(filename=config['paths']['logs'], level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def train():
    print("Fetching data...")
    df = fetch_data(limit=2000)
    
    if df is None:
        print("Failed to fetch data.")
        return

    print("Adding indicators...")
    df = add_indicators(df)
    
    # Define features and target
    features = [
        'return', 'sma_20', 'sma_50', 'ema_12', 'rsi', 'volatility',
        'return_lag_1', 'return_lag_2', 'return_lag_3',
        'rsi_lag_1', 'rsi_lag_2', 'rsi_lag_3',
        'volatility_lag_1', 'volatility_lag_2', 'volatility_lag_3'
    ]
    
    X = df[features]
    y = df['target']
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    
    # Initialize model with config params
    params = config['model_params']
    model = RandomForestClassifier(
        n_estimators=params['n_estimators'],
        max_depth=params['max_depth'],
        min_samples_leaf=params['min_samples_leaf'],
        random_state=params['random_state']
    )
    
    print("Training model...")
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
    print(f"Model saved to {model_path}")
    
    logging.info(f"Model trained. Accuracy: {acc:.4f}")

if __name__ == "__main__":
    train()
