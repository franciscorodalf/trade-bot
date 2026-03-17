"""
FastAPI REST API for the AI Trading Bot.

Serves real-time trading data, scanner results, portfolio statistics,
and bot control endpoints to the web dashboard.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import json
import sys
import os
import pandas as pd
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

# ---- App Setup ----

app = FastAPI(
    title="AI Trading Bot API",
    description="REST API for the quantitative trading bot dashboard",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Configuration ----

with open('config.json', 'r') as f:
    config = json.load(f)

DB_PATH: str = config['paths']['database']

# Ensure bot module is importable
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'bot'))


# ---- Database Helper ----

@contextmanager
def get_db():
    """Context manager for safe database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ---- Endpoints ----

@app.get("/balance", tags=["Portfolio"])
def get_balance() -> Dict[str, Any]:
    """Get the latest portfolio balance and equity."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM balance_history ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row:
        return dict(row)
    return {"balance": 0, "equity": 0}


@app.get("/trades", tags=["Portfolio"])
def get_trades(limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent trade history, ordered newest first."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


@app.get("/live-signal", tags=["Scanner"])
def get_live_signal() -> Dict[str, Any]:
    """Get the most recent ML prediction signal."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM signals ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row:
        return dict(row)
    return {}


@app.get("/statistics", tags=["Portfolio"])
def get_statistics() -> Dict[str, Any]:
    """
    Calculate portfolio performance metrics from closed trades.

    Returns:
        Dict with winrate (%), total_trades count, and cumulative pnl.
    """
    with get_db() as conn:
        trades = conn.execute(
            "SELECT * FROM trades WHERE status='CLOSED'"
        ).fetchall()

    if not trades:
        return {"winrate": 0, "total_trades": 0, "pnl": 0}

    df = pd.DataFrame([dict(t) for t in trades])
    total_trades: int = len(df)
    winning_trades: int = len(df[df['pnl'] > 0])
    winrate: float = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    total_pnl: float = df['pnl'].sum()

    return {
        "winrate": round(winrate, 2),
        "total_trades": total_trades,
        "pnl": round(total_pnl, 8)
    }


@app.get("/scanner", tags=["Scanner"])
def get_scanner() -> List[Dict[str, Any]]:
    """
    Get the latest ML signal for each configured symbol.

    Results are sorted by prediction confidence (probability) descending.
    Only returns symbols that are in the current config.
    """
    with get_db() as conn:
        query = """
        SELECT * FROM signals
        WHERE id IN (
            SELECT MAX(id) FROM signals GROUP BY symbol
        )
        ORDER BY probability DESC
        """
        rows = conn.execute(query).fetchall()

    valid_symbols = set(config.get('symbols', []))
    return [dict(row) for row in rows if row['symbol'] in valid_symbols]


@app.get("/chart-data", tags=["Charts"])
def get_chart_data(
    symbol: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Fetch OHLCV candlestick data formatted for TradingView Lightweight Charts.

    Args:
        symbol: Trading pair (e.g. 'BTC/USDT'). Defaults to config.
        limit: Number of candles to return.
    """
    from utils import fetch_data

    df = fetch_data(symbol=symbol, limit=limit)
    if df is None:
        return []

    return [
        {
            "time": int(index.timestamp()),
            "open": row['open'],
            "high": row['high'],
            "low": row['low'],
            "close": row['close'],
            "volume": row['volume']
        }
        for index, row in df.iterrows()
    ]


@app.get("/logs", tags=["System"])
def get_logs(limit: int = 20) -> Dict[str, List[str]]:
    """
    Read the last N lines from the bot's log file.

    Args:
        limit: Number of log lines to return (default 20).
    """
    log_path = config['paths']['logs']
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
        return {"logs": [line.strip() for line in lines[-limit:]]}
    except FileNotFoundError:
        return {"logs": ["Log file not found. Bot may not have started yet."]}
    except Exception as e:
        return {"logs": [f"Error reading logs: {str(e)}"]}


# ---- Control ----

class ControlRequest(BaseModel):
    """Request body for bot control actions."""
    action: str  # 'pause' or 'resume'


@app.post("/control", tags=["System"])
def control_bot(req: ControlRequest) -> Dict[str, str]:
    """
    Pause or resume the trading bot.

    The bot checks bot_status.json each cycle to determine
    whether to continue operating or sleep.
    """
    status_file = "bot_status.json"

    if req.action == "pause":
        with open(status_file, "w") as f:
            json.dump({"paused": True}, f)
        return {"status": "paused"}
    elif req.action == "resume":
        with open(status_file, "w") as f:
            json.dump({"paused": False}, f)
        return {"status": "running"}

    raise HTTPException(status_code=400, detail="Invalid action. Use 'pause' or 'resume'.")


# ---- Entry Point ----

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
