import joblib
import pandas as pd
import json
import logging
import os
import asyncio

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

logging.basicConfig(filename=config['paths']['logs'], level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Global cache for the model
_model_cache = None

def load_model():
    global _model_cache
    if _model_cache is not None:
        return _model_cache

    model_path = config['paths']['model']
    if not os.path.exists(model_path):
        logging.error("Model file not found. Please train the model first.")
        return None
    
    logging.info(f"Loading model from {model_path}...")
    _model_cache = joblib.load(model_path)
    return _model_cache

async def predict_symbol(symbol=None):
    model = load_model()
    if model is None:
        return None

    # Determine symbol (if None, let utils handle it via config)
    # But for multi-symbol we usually pass it.
    
    # We need to ensure we fetch data FOR THAT symbol
    from utils import fetch_data, add_indicators
    
    # Custom fetch for prediction to ensure we get the right symbol's data
    # utils.fetch_data handles the default if symbol is None
    # Now ASYNC awaiting
    df = await fetch_data(symbol=symbol, limit=1000)
    
    if df is not None:
        df = add_indicators(df)

    if df is None or df.empty:
        logging.error(f"No data available for prediction on {symbol}.")
        return None
    
    # Get the last row (most recent completed candle)
    last_row = df.iloc[-1]
    
    # Check volatility
    volatility = last_row['volatility']
    vol_threshold = config['volatility_threshold']
    
    if volatility < vol_threshold:
        logging.info(f"[{symbol}] Volatility too low ({volatility:.4f} < {vol_threshold}). Skipping prediction.")
        return {
            "signal": "HOLD",
            "probability": 0.0,
            "volatility": volatility,
            "close": last_row['close'],
            "reason": "Low Volatility"
        }

    # Prepare features
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
        
    logging.info(f"[{symbol}] Prediction: {signal} (Prob: {prob:.4f}, Close: {last_row['close']:.8f})")
    
    return {
        "signal": signal,
        "probability": prob,
        "volatility": volatility,
        "atr": last_row['atr'],
        "close": last_row['close'],
        "reason": "Model Signal"
    }

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    print(loop.run_until_complete(predict_symbol()))
