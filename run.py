#!/usr/bin/env python3
"""
Unified launcher for the Polymarket BTC Prediction Bot.

Starts the prediction bot, API server, and web dashboard
in a single process using asyncio and subprocesses.

Usage:
    python run.py              # Start all services
    python run.py --train      # Train model first, then start
    python run.py --backtest   # Run backtest only
"""

import argparse
import asyncio
import os
import signal
import subprocess
import sys


def ensure_dirs():
    """Create required directories."""
    for d in ["database", "logs", "bot/models"]:
        os.makedirs(d, exist_ok=True)


def run_training():
    """Run model training pipeline."""
    print("\n  [1/2] Training XGBoost model...\n")
    result = subprocess.run(
        [sys.executable, "bot/train_model.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    if result.returncode != 0:
        print("  [ERROR] Training failed.")
        sys.exit(1)
    print("  [OK] Model trained successfully.\n")


def run_backtest():
    """Run backtesting pipeline."""
    print("\n  Running backtest...\n")
    subprocess.run(
        [sys.executable, "bot/backtest.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )


async def start_all():
    """Start bot, API, and web server concurrently."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    bot_dir = os.path.join(project_root, "bot")
    procs = []

    print("\n  Starting Polymarket BTC Prediction Bot")
    print("  " + "=" * 45)

    # API server
    api_proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "uvicorn", "api.main:app",
        "--host", "0.0.0.0", "--port", "8000", "--reload",
        cwd=project_root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    procs.append(("API", api_proc))
    print("  [OK] API server     → http://localhost:8000")
    print("  [OK] Dashboard      → http://localhost:8000/")

    # Bot (paper trading)
    bot_proc = await asyncio.create_subprocess_exec(
        sys.executable, "paper_trading.py",
        cwd=bot_dir,
        stdout=None,  # Let bot print to console
        stderr=None,
    )
    procs.append(("Bot", bot_proc))
    print("  [OK] Prediction bot → started")
    print("  " + "=" * 45)
    print("  Press Ctrl+C to stop all services.\n")

    # Wait for any process to exit
    try:
        done, _ = await asyncio.wait(
            [asyncio.create_task(p.wait()) for _, p in procs],
            return_when=asyncio.FIRST_COMPLETED,
        )
    except asyncio.CancelledError:
        pass
    finally:
        for name, proc in procs:
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    proc.kill()
        print("\n  All services stopped.")


def main():
    parser = argparse.ArgumentParser(description="Polymarket BTC Prediction Bot")
    parser.add_argument("--train", action="store_true", help="Train model before starting")
    parser.add_argument("--backtest", action="store_true", help="Run backtest only")
    args = parser.parse_args()

    ensure_dirs()

    if args.backtest:
        run_backtest()
        return

    if args.train:
        run_training()

    # Check if model exists
    if not os.path.exists("bot/models/model.pkl"):
        print("\n  [!] No trained model found.")
        print("  Run: python run.py --train")
        print("  Or:  cd bot && python train_model.py\n")
        sys.exit(1)

    # Handle Ctrl+C gracefully
    def shutdown(sig, frame):
        print("\n  Shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)

    asyncio.run(start_all())


if __name__ == "__main__":
    main()
