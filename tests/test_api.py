"""
Tests for the FastAPI backend.
Covers: all REST endpoints, response formats, edge cases.
"""

import pytest
import json
import sqlite3
import os
import sys

# We need to set up config.json before importing the FastAPI app


@pytest.fixture
def app_client(config_with_paths, tmp_dir, test_db):
    """Create a FastAPI test client with mocked config and database."""
    # Write config.json to temp dir
    config_path = tmp_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(config_with_paths, f)

    # Write bot_status.json
    status_path = tmp_dir / "bot_status.json"
    with open(status_path, "w") as f:
        json.dump({"paused": False}, f)

    # Write a fake log file
    log_path = config_with_paths["paths"]["logs"]
    with open(log_path, "w") as f:
        f.write("2026-03-17 10:00:00 [INFO] Bot started\n")
        f.write("2026-03-17 10:01:00 [INFO] Scanning market...\n")
        f.write("2026-03-17 10:01:05 [INFO] BUY BTC/USDT @ 50000\n")

    # Change to temp dir so config.json is found
    original_dir = os.getcwd()
    os.chdir(str(tmp_dir))

    # Clear cached module imports
    for mod_name in list(sys.modules.keys()):
        if 'api' in mod_name or 'main' in mod_name:
            del sys.modules[mod_name]

    sys.path.insert(0, str(tmp_dir))
    sys.path.insert(0, os.path.join(str(tmp_dir), '..'))

    # Import after setup
    from fastapi.testclient import TestClient
    # Need to re-import since it reads config.json on import
    from api.main import app

    client = TestClient(app)
    yield client

    os.chdir(original_dir)


# ============================================
# Balance Endpoint
# ============================================

class TestBalanceEndpoint:
    def test_get_balance_returns_data(self, app_client):
        """GET /balance should return balance and equity."""
        response = app_client.get("/balance")

        assert response.status_code == 200
        data = response.json()
        assert "balance" in data
        assert "equity" in data

    def test_balance_values_are_numeric(self, app_client):
        """Balance and equity should be numeric values."""
        data = app_client.get("/balance").json()

        assert isinstance(data["balance"], (int, float))
        assert isinstance(data["equity"], (int, float))

    def test_balance_matches_db(self, app_client, config_with_paths):
        """Balance should match the latest entry in the database."""
        data = app_client.get("/balance").json()

        # Our test_db fixture inserts balance=100.0, equity=105.0
        assert data["balance"] == 100.0
        assert data["equity"] == 105.0


# ============================================
# Trades Endpoint
# ============================================

class TestTradesEndpoint:
    def test_get_trades_returns_list(self, app_client):
        """GET /trades should return a list."""
        response = app_client.get("/trades")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_trades_have_required_fields(self, app_client):
        """Each trade should have standard fields."""
        data = app_client.get("/trades").json()

        if len(data) > 0:
            trade = data[0]
            required_fields = ["symbol", "side", "price", "amount", "pnl", "status"]
            for field in required_fields:
                assert field in trade, f"Trade missing field: {field}"

    def test_trades_limit_parameter(self, app_client):
        """Limit parameter should cap the number of trades returned."""
        data = app_client.get("/trades?limit=2").json()

        assert len(data) <= 2

    def test_trades_default_limit(self, app_client):
        """Default should return up to 50 trades."""
        data = app_client.get("/trades").json()

        assert len(data) <= 50


# ============================================
# Statistics Endpoint
# ============================================

class TestStatisticsEndpoint:
    def test_get_statistics_returns_data(self, app_client):
        """GET /statistics should return winrate, total_trades, pnl."""
        response = app_client.get("/statistics")

        assert response.status_code == 200
        data = response.json()
        assert "winrate" in data
        assert "total_trades" in data
        assert "pnl" in data

    def test_winrate_is_percentage(self, app_client):
        """Win rate should be between 0 and 100."""
        data = app_client.get("/statistics").json()

        assert 0 <= data["winrate"] <= 100

    def test_statistics_match_db(self, app_client):
        """Statistics should match our test data (1 win, 1 loss = 50% WR)."""
        data = app_client.get("/statistics").json()

        # test_db has 2 CLOSED trades: 1 with pnl=2.0, 1 with pnl=-1.65
        assert data["total_trades"] == 2
        assert data["winrate"] == 50.0
        assert abs(data["pnl"] - 0.35) < 0.01  # 2.0 + (-1.65) = 0.35


# ============================================
# Scanner Endpoint
# ============================================

class TestScannerEndpoint:
    def test_get_scanner_returns_list(self, app_client):
        """GET /scanner should return a list of signals."""
        response = app_client.get("/scanner")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_scanner_signals_have_required_fields(self, app_client):
        """Each scanner entry should have symbol, signal_type, probability."""
        data = app_client.get("/scanner").json()

        for entry in data:
            assert "symbol" in entry
            assert "signal_type" in entry
            assert "probability" in entry

    def test_scanner_sorted_by_probability(self, app_client):
        """Results should be sorted by probability descending."""
        data = app_client.get("/scanner").json()

        if len(data) >= 2:
            probs = [d["probability"] for d in data]
            assert probs == sorted(probs, reverse=True)

    def test_scanner_filters_valid_symbols(self, app_client):
        """Should only return configured symbols."""
        data = app_client.get("/scanner").json()
        valid = {"BTC/USDT", "ETH/USDT"}

        for entry in data:
            assert entry["symbol"] in valid, f"Unexpected symbol: {entry['symbol']}"


# ============================================
# Live Signal Endpoint
# ============================================

class TestLiveSignalEndpoint:
    def test_get_live_signal(self, app_client):
        """GET /live-signal should return the latest signal."""
        response = app_client.get("/live-signal")

        assert response.status_code == 200
        data = response.json()
        # Should return the last inserted signal (HOLD for BTC/USDT)
        assert "symbol" in data or data == {}


# ============================================
# Logs Endpoint
# ============================================

class TestLogsEndpoint:
    def test_get_logs_returns_list(self, app_client):
        """GET /logs should return a list of log lines."""
        response = app_client.get("/logs")

        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert isinstance(data["logs"], list)

    def test_logs_limit_parameter(self, app_client):
        """Limit parameter should cap the number of log lines."""
        data = app_client.get("/logs?limit=2").json()

        assert len(data["logs"]) <= 2

    def test_logs_contain_content(self, app_client):
        """Logs should contain the test log content we wrote."""
        data = app_client.get("/logs").json()

        assert len(data["logs"]) > 0
        combined = " ".join(data["logs"])
        assert "Bot started" in combined


# ============================================
# Control Endpoint
# ============================================

class TestControlEndpoint:
    def test_pause_bot(self, app_client):
        """POST /control with pause should return paused status."""
        response = app_client.post("/control", json={"action": "pause"})

        assert response.status_code == 200
        assert response.json()["status"] == "paused"

    def test_resume_bot(self, app_client):
        """POST /control with resume should return running status."""
        response = app_client.post("/control", json={"action": "resume"})

        assert response.status_code == 200
        assert response.json()["status"] == "running"

    def test_invalid_action(self, app_client):
        """POST /control with invalid action should return 400."""
        response = app_client.post("/control", json={"action": "invalid"})

        assert response.status_code == 400
