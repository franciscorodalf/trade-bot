#!/usr/bin/env python3
"""
Unified launcher for the AI Trading Bot system.

Starts all three services (Bot, API, Web) in a single terminal
using multiprocessing. Press Ctrl+C to gracefully stop all services.

Usage:
    python run.py              # Start all services
    python run.py --no-bot     # Start API + Web only (for development)
    python run.py --no-web     # Start Bot + API only
"""

import subprocess
import sys
import os
import signal
import time
import argparse
from typing import List, Optional

# ANSI colors for terminal output
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


BANNER = f"""
{Colors.CYAN}{Colors.BOLD}
    ╔═══════════════════════════════════════╗
    ║     AI Quantitative Trading Bot       ║
    ║         Command Center                ║
    ╚═══════════════════════════════════════╝
{Colors.RESET}"""

processes: List[subprocess.Popen] = []


def log(service: str, message: str, color: str = Colors.DIM) -> None:
    """Print a formatted log message."""
    print(f"  {color}[{service}]{Colors.RESET} {message}")


def start_service(
    name: str,
    command: List[str],
    color: str,
    cwd: Optional[str] = None
) -> Optional[subprocess.Popen]:
    """Start a service as a subprocess."""
    try:
        proc = subprocess.Popen(
            command,
            cwd=cwd or os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        processes.append(proc)
        log(name, f"Started (PID: {proc.pid})", color)
        return proc
    except Exception as e:
        log(name, f"Failed to start: {e}", Colors.RED)
        return None


def shutdown(signum=None, frame=None) -> None:
    """Gracefully terminate all services."""
    print(f"\n\n  {Colors.YELLOW}Shutting down all services...{Colors.RESET}")

    for proc in processes:
        try:
            proc.terminate()
        except Exception:
            pass

    # Wait up to 5 seconds for graceful exit
    deadline = time.time() + 5
    for proc in processes:
        remaining = max(0, deadline - time.time())
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            proc.kill()

    print(f"  {Colors.GREEN}All services stopped.{Colors.RESET}\n")
    sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Trading Bot Launcher")
    parser.add_argument('--no-bot', action='store_true', help='Skip starting the trading bot')
    parser.add_argument('--no-web', action='store_true', help='Skip starting the web server')
    parser.add_argument('--no-api', action='store_true', help='Skip starting the API server')
    parser.add_argument('--api-port', type=int, default=8000, help='API server port (default: 8000)')
    parser.add_argument('--web-port', type=int, default=5500, help='Web server port (default: 5500)')
    args = parser.parse_args()

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(BANNER)

    python = sys.executable
    project_root = os.path.dirname(os.path.abspath(__file__))

    # Ensure required directories exist
    for d in ['database', 'logs', 'bot/models']:
        os.makedirs(os.path.join(project_root, d), exist_ok=True)

    # Check if model exists
    model_path = os.path.join(project_root, 'bot', 'models', 'model.pkl')
    if not os.path.exists(model_path):
        print(f"  {Colors.YELLOW}[!] No trained model found.{Colors.RESET}")
        print(f"      Run: {Colors.BOLD}python bot/train_model.py{Colors.RESET}\n")

    services_started = 0

    # Start API Server
    if not args.no_api:
        start_service(
            "API",
            [python, "-m", "uvicorn", "api.main:app",
             "--host", "0.0.0.0", "--port", str(args.api_port)],
            Colors.BLUE
        )
        services_started += 1
        time.sleep(1)  # Let API initialize first

    # Start Trading Bot
    if not args.no_bot:
        start_service(
            "BOT",
            [python, "bot/paper_trading.py"],
            Colors.GREEN
        )
        services_started += 1

    # Start Web Dashboard
    if not args.no_web:
        start_service(
            "WEB",
            [python, "-m", "http.server", str(args.web_port)],
            Colors.CYAN,
            cwd=os.path.join(project_root, "web")
        )
        services_started += 1

    if services_started == 0:
        print(f"  {Colors.RED}No services to start!{Colors.RESET}")
        return

    # Print status
    print(f"\n  {Colors.GREEN}{Colors.BOLD}All services running!{Colors.RESET}\n")

    if not args.no_web:
        print(f"  {Colors.CYAN}Dashboard:{Colors.RESET}  http://localhost:{args.web_port}")
    if not args.no_api:
        print(f"  {Colors.BLUE}API Docs:{Colors.RESET}   http://localhost:{args.api_port}/docs")

    print(f"\n  {Colors.DIM}Press Ctrl+C to stop all services{Colors.RESET}\n")

    # Keep main process alive, watching for child exits
    try:
        while True:
            for proc in processes:
                if proc.poll() is not None:
                    log("SYSTEM", f"Process {proc.pid} exited unexpectedly", Colors.RED)
            time.sleep(2)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
