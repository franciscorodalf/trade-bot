import joblib
import pandas as pd
import json
import logging
import os
from utils import get_latest_data_with_indicators

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

logging.basicConfig(filename=config['paths']['logs'], level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def load_model():
    model_path = config['paths']['model']
    if not os.path.exists(model_path):
        logging.error("Model file not found. Please train the model first.")
        return None
    return joblib.load(model_path)

def predict():
    model = load_model()
    if model is None:
        return None

    df = get_latest_data_with_indicators()
    if df is None or df.empty:
        logging.error("No data available for prediction.")
        return None
    
    # Get the last row (most recent completed candle)
    last_row = df.iloc[-1]
    
    # Check volatility
    volatility = last_row['volatility']
    vol_threshold = config['volatility_threshold']
    
    if volatility < vol_threshold:
        logging.info(f"Volatility too low ({volatility:.4f} < {vol_threshold}). Skipping prediction.")
        return {
            "signal": "HOLD",
            "probability": 0.0,
            "volatility": volatility,
            "close": last_row['close'],
            "reason": "Low Volatility"
        }

    # Prepare features
    features = [
        'return', 'sma_20', 'sma_50', 'ema_12', 'rsi', 'volatility',
        'return_lag_1', 'return_lag_2', 'return_lag_3',
        'rsi_lag_1', 'rsi_lag_2', 'rsi_lag_3',
        'volatility_lag_1', 'volatility_lag_2', 'volatility_lag_3'
    ]
    
    X_new = pd.DataFrame([last_row[features]])
    
    # Predict probability
    prob = model.predict_proba(X_new)[0][1] # Probability of class 1 (Up)
    
    buy_threshold = config['buy_threshold']
    sell_threshold = config['sell_threshold']
    
    signal = "HOLD"
    if prob > buy_threshold:
        signal = "BUY"
    elif prob < sell_threshold:
        signal = "SELL"
        
    logging.info(f"Prediction: {signal} (Prob: {prob:.4f}, Close: {last_row['close']:.2f})")
    
    return {
        "signal": signal,
        "probability": prob,
        "volatility": volatility,
        "close": last_row['close'],
        "reason": "Model Signal"
    }

if __name__ == "__main__":
    print(predict())
