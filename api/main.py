"""
FastAPI REST API for the Polymarket BTC Prediction Bot.

Serves prediction data, bet history, performance metrics,
and bot control endpoints to the web dashboard.
"""

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

# Load config
config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
with open(config_path, "r") as f:
    config = json.load(f)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", config["paths"]["database"])

app = FastAPI(
    title="Polymarket BTC Prediction Bot API",
    description="Real-time prediction data and bet tracking for BTC 5-min markets",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@contextmanager
def get_db():
    """Context manager for database access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def row_to_dict(row) -> Dict[str, Any]:
    """Convert sqlite3.Row to dict."""
    return dict(row) if row else {}


# ---- Status ----

@app.get("/api/status")
def get_status():
    """Get bot status and current balance."""
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM balance_history ORDER BY id DESC LIMIT 1"
            ).fetchone()

            total_bets = conn.execute("SELECT COUNT(*) as c FROM bets").fetchone()
            pending = conn.execute(
                "SELECT COUNT(*) as c FROM bets WHERE result='PENDING'"
            ).fetchone()

        return {
            "status": "running",
            "bankroll": row["bankroll"] if row else config["trading"]["initial_capital"],
            "equity": row["equity"] if row else config["trading"]["initial_capital"],
            "total_pnl": row["total_pnl"] if row else 0,
            "win_rate": row["win_rate"] if row else 0,
            "total_bets": total_bets["c"] if total_bets else 0,
            "pending_bets": pending["c"] if pending else 0,
        }
    except Exception:
        return {
            "status": "idle",
            "bankroll": config["trading"]["initial_capital"],
            "equity": config["trading"]["initial_capital"],
            "total_pnl": 0,
            "win_rate": 0,
            "total_bets": 0,
            "pending_bets": 0,
        }


# ---- Balance History ----

@app.get("/api/balance")
def get_balance_history(limit: int = 200):
    """Get balance history for equity curve chart."""
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT bankroll, equity, total_pnl, win_rate, total_bets, timestamp "
                "FROM balance_history ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [row_to_dict(r) for r in reversed(rows)]
    except Exception:
        return []


# ---- Bets ----

@app.get("/api/bets")
def get_bets(limit: int = 50, status: Optional[str] = None):
    """Get bet history, optionally filtered by status."""
    try:
        with get_db() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM bets WHERE result=? ORDER BY timestamp DESC LIMIT ?",
                    (status.upper(), limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM bets ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [row_to_dict(r) for r in rows]
    except Exception:
        return []


@app.get("/api/bets/stats")
def get_bet_stats():
    """Get aggregated bet statistics."""
    try:
        with get_db() as conn:
            total = conn.execute("SELECT COUNT(*) as c FROM bets").fetchone()["c"]
            wins = conn.execute(
                "SELECT COUNT(*) as c FROM bets WHERE result='WIN'"
            ).fetchone()["c"]
            losses = conn.execute(
                "SELECT COUNT(*) as c FROM bets WHERE result='LOSS'"
            ).fetchone()["c"]
            pending = conn.execute(
                "SELECT COUNT(*) as c FROM bets WHERE result='PENDING'"
            ).fetchone()["c"]
            total_pnl = conn.execute(
                "SELECT COALESCE(SUM(pnl), 0) as s FROM bets WHERE result != 'PENDING'"
            ).fetchone()["s"]
            avg_edge = conn.execute(
                "SELECT COALESCE(AVG(edge), 0) as a FROM bets"
            ).fetchone()["a"]
            avg_bet = conn.execute(
                "SELECT COALESCE(AVG(amount), 0) as a FROM bets"
            ).fetchone()["a"]

        return {
            "total": total,
            "wins": wins,
            "losses": losses,
            "pending": pending,
            "win_rate": wins / total if total > 0 else 0,
            "total_pnl": total_pnl,
            "avg_edge": avg_edge,
            "avg_bet_size": avg_bet,
        }
    except Exception:
        return {"total": 0, "wins": 0, "losses": 0, "pending": 0,
                "win_rate": 0, "total_pnl": 0, "avg_edge": 0, "avg_bet_size": 0}


# ---- Predictions ----

@app.get("/api/predictions")
def get_predictions(limit: int = 50):
    """Get recent prediction history."""
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM predictions ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [row_to_dict(r) for r in rows]
    except Exception:
        return []


# ---- Model Metrics ----

@app.get("/api/model/metrics")
def get_model_metrics():
    """Get latest model training/backtest metrics."""
    metrics_path = os.path.join(
        os.path.dirname(__file__), "..", config["paths"]["backtest_results"]
    )
    try:
        with open(metrics_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": "No metrics available. Run training or backtest first."}


# ---- Config ----

@app.get("/api/config")
def get_config():
    """Get trading configuration (excluding secrets)."""
    safe_config = {
        "trading": config["trading"],
        "model": {
            "type": config["model"]["type"],
            "buy_threshold": config["model"]["buy_threshold"],
            "sell_threshold": config["model"]["sell_threshold"],
            "calibration": config["model"]["calibration"],
        },
        "features": config["features"],
    }
    return safe_config


# ---- Static Files (Dashboard) ----

web_path = os.path.join(os.path.dirname(__file__), "..", "web")
if os.path.exists(web_path):
    app.mount("/static", StaticFiles(directory=web_path), name="static")

    @app.get("/")
    def serve_dashboard():
        index_path = os.path.join(web_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="Dashboard not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
