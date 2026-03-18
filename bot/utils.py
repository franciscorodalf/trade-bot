"""
Shared utilities for the Polymarket BTC prediction bot.

Provides helper functions for logging setup, config loading,
and common operations used across modules.
"""

import json
import logging
import os
from typing import Dict, Any


def load_config(path: str = "config.json") -> Dict[str, Any]:
    """Load configuration from JSON file."""
    with open(path, "r") as f:
        return json.load(f)


def setup_logging(log_file: str = "logs/bot.log", level: int = logging.INFO) -> None:
    """Configure logging with both file and console handlers."""
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file),
        ],
    )


def ensure_directories() -> None:
    """Create required directories if they don't exist."""
    dirs = ["database", "logs", "bot/models"]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
