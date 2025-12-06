import pandas as pd
import numpy as np
import json
import logging
from utils import fetch_data, add_indicators
from strategy import Strategy
import joblib
import os

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

logging.basicConfig(filename=config['paths']['logs'], level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def run_backtest():
    print("Starting Backtest...")
    
    # Load Model
    model_path = config['paths']['model']
    if not os.path.exists(model_path):
        print("Model not found. Please train first.")
        return
    model = joblib.load(model_path)
    
    # Fetch Data
    df = fetch_data(limit=2000)
    if df is None:
        print("No data.")
        return
    df = add_indicators(df)
    
    # Prepare features
    features = [
        'return', 'sma_20', 'sma_50', 'ema_12', 'rsi', 'volatility',
        'return_lag_1', 'return_lag_2', 'return_lag_3',
        'rsi_lag_1', 'rsi_lag_2', 'rsi_lag_3',
        'volatility_lag_1', 'volatility_lag_2', 'volatility_lag_3'
    ]
    
    # Simulation variables
    balance = config['initial_capital']
    equity_curve = []
    trades = []
    strategy = Strategy()
    
    print(f"Initial Balance: {balance}")
    
    for i in range(len(df)):
        if i < 50: continue # Skip initial warmup
        
        row = df.iloc[i]
        current_price = row['close']
        
        # Predict
        X_new = pd.DataFrame([row[features]])
        prob = model.predict_proba(X_new)[0][1]
        
        pred_signal = "HOLD"
        if prob > config['buy_threshold']:
            pred_signal = "BUY"
        elif prob < config['sell_threshold']:
            pred_signal = "SELL"
            
        prediction = {
            "signal": pred_signal,
            "probability": prob
        }
        
        # Get Strategy Decision
        decision = strategy.get_signal(prediction, current_price)
        
        # Execute Decision (Simulation)
        if decision['action'] == "BUY":
            # Calculate quantity
            # Simple: use all balance (minus commission)
            cost = balance * (1 - config['commission_rate'])
            amount = cost / current_price
            
            # Apply slippage
            exec_price = current_price * (1 + config['slippage'])
            
            strategy.update_position("BUY", exec_price, decision['sl'], decision['tp'])
            
            trades.append({
                "type": "BUY",
                "price": exec_price,
                "amount": amount,
                "time": row.name,
                "balance": balance
            })
            
            # Update balance (converted to asset)
            # In this simple simulation, we track 'balance' as Quote currency (USDT/EUR)
            # When we buy, balance goes to 0, but we hold asset.
            # To simplify PnL tracking, we'll keep balance as is until SELL.
            # But strictly, balance = 0, position_value = amount * price.
            
            # Let's track 'held_amount'
            held_amount = amount
            balance = 0 
            
        elif decision['action'] == "SELL":
            if strategy.position == "NONE": continue # Should be handled by strategy, but double check
            
            # Sell everything
            exec_price = current_price * (1 - config['slippage'])
            revenue = held_amount * exec_price * (1 - config['commission_rate'])
            
            balance = revenue
            held_amount = 0
            
            strategy.update_position("SELL", exec_price)
            
            trades.append({
                "type": "SELL",
                "price": exec_price,
                "reason": decision['reason'],
                "time": row.name,
                "balance": balance
            })
            
        # Track Equity
        if strategy.position == "LONG":
            current_equity = held_amount * current_price
        else:
            current_equity = balance
            
        equity_curve.append(current_equity)
        
    # Calculate Final Equity
    final_equity = balance
    if strategy.position == "LONG":
        final_equity = held_amount * df.iloc[-1]['close']
        
    print(f"Final Equity: {final_equity:.2f}")
    print(f"Total Trades: {len(trades)}")
    
    # Calculate Metrics
    equity_series = pd.Series(equity_curve)
    returns = equity_series.pct_change().dropna()
    sharpe = returns.mean() / returns.std() * np.sqrt(24*365) if returns.std() != 0 else 0
    
    print(f"Sharpe Ratio: {sharpe:.2f}")
    
    # Save results to CSV for analysis if needed
    pd.DataFrame(trades).to_csv("backtest_trades.csv")

if __name__ == "__main__":
    run_backtest()
