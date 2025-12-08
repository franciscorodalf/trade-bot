from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import json
import pandas as pd
from pydantic import BaseModel
from typing import List, Optional
import sys
import os

# Add bot directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'bot'))
from utils import fetch_data

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
def get_trades(limit: int = 50, symbol: str = None):
    conn = get_db_connection()
    try:
        if symbol:
            rows = conn.execute("SELECT * FROM trades WHERE symbol = ? ORDER BY id DESC LIMIT ?", (symbol, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

@app.get("/live-signal")
def get_live_signal():
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM signals ORDER BY id DESC LIMIT 1").fetchone()
        if row:
            return dict(row)
        return {}
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()

@app.get("/statistics")
def get_statistics():
    conn = get_db_connection()
    try:
        trades = conn.execute("SELECT * FROM trades WHERE status='CLOSED'").fetchall()
    except sqlite3.OperationalError:
         return {"winrate": 0, "total_trades": 0, "pnl": 0}
    finally:
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
        "pnl": round(total_pnl, 8)
    }

@app.get("/scanner")
def get_scanner():
    """
    Get the latest signal for every symbol.
    """
    conn = get_db_connection()
    # Get unique symbols first or just group by symbol
    # Simple query: Get latest entry for each symbol
    # SQLite distinct on/group by trick
    query = """
    SELECT * FROM signals 
    WHERE id IN (
        SELECT MAX(id) 
        FROM signals 
        GROUP BY symbol
    )
    ORDER BY probability DESC
    """
    try:
        rows = conn.execute(query).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    
    # Filter by configured symbols only to avoid legacy data issues
    valid_symbols = set(config.get('symbols', []))
    results = [dict(row) for row in rows if row['symbol'] in valid_symbols]
    
    return results

@app.get("/chart-data")
async def get_chart_data(symbol: Optional[str] = None, limit: int = 100):
    # Async endpoint because it awaits fetch_data
    df = await fetch_data(symbol=symbol, limit=limit)
    if df is None:
        return []
        
    # Format for TradingView Lightweight Charts
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

@app.get("/logs")
def get_logs(limit: int = 20):
    log_path = config['paths']['logs']
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
            # Return last N lines
            return {"logs": [line.strip() for line in lines[-limit:]]}
    except Exception as e:
        return {"logs": [f"Error reading logs: {str(e)}"]}

class ControlRequest(BaseModel):
    action: str # 'pause', 'resume'

@app.post("/control")
def control_bot(req: ControlRequest):
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
