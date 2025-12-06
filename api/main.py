from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import json
import pandas as pd
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)
    
DB_PATH = config['paths']['database']

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/balance")
def get_balance():
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM balance_history ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"balance": 0, "equity": 0}

@app.get("/trades")
def get_trades(limit: int = 50):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/live-signal")
def get_live_signal():
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM signals ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if row:
        return dict(row)
    return {}

@app.get("/statistics")
def get_statistics():
    conn = get_db_connection()
    trades = conn.execute("SELECT * FROM trades WHERE status='CLOSED'").fetchall()
    conn.close()
    
    if not trades:
        return {"winrate": 0, "total_trades": 0, "pnl": 0}
        
    df = pd.DataFrame([dict(t) for t in trades])
    total_trades = len(df)
    winning_trades = len(df[df['pnl'] > 0])
    winrate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    total_pnl = df['pnl'].sum()
    
    return {
        "winrate": round(winrate, 2),
        "total_trades": total_trades,
        "pnl": round(total_pnl, 2)
    }

@app.get("/chart-data")
def get_chart_data(limit: int = 100):
    # In a real app, we'd fetch this from DB if we stored OHLC there, 
    # or proxy to yfinance/exchange. For now, let's use yfinance via utils.
    # But importing utils here might be slow or cause issues if not careful.
    # Let's just read from a local CSV if we had one, or fetch fresh.
    # For speed, let's fetch fresh but cache it or similar.
    # To keep it simple and robust as requested:
    
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'bot'))
    from utils import fetch_data
    
    df = fetch_data(limit=limit)
    if df is None:
        return []
        
    # Format for TradingView Lightweight Charts
    # Time needs to be unix timestamp
    data = []
    for index, row in df.iterrows():
        data.append({
            "time": int(index.timestamp()),
            "open": row['open'],
            "high": row['high'],
            "low": row['low'],
            "close": row['close'],
            "volume": row['volume']
        })
    return data

class ControlRequest(BaseModel):
    action: str # 'pause', 'resume'

@app.post("/control")
def control_bot(req: ControlRequest):
    # In a real app, we'd communicate with the bot process via DB or IPC.
    # Here we can write a status file that the bot checks.
    status_file = "bot_status.json"
    
    if req.action == "pause":
        with open(status_file, "w") as f:
            json.dump({"paused": True}, f)
        return {"status": "paused"}
    elif req.action == "resume":
        with open(status_file, "w") as f:
            json.dump({"paused": False}, f)
        return {"status": "running"}
    
    raise HTTPException(status_code=400, detail="Invalid action")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
