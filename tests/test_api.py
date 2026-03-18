"""Tests for the FastAPI endpoints."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


class TestStatusEndpoint:
    def test_status_returns_200(self):
        response = client.get("/api/status")
        assert response.status_code == 200

    def test_status_has_required_fields(self):
        data = client.get("/api/status").json()
        assert "status" in data
        assert "bankroll" in data
        assert "total_pnl" in data
        assert "win_rate" in data


class TestBalanceEndpoint:
    def test_balance_returns_list(self):
        response = client.get("/api/balance")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestBetsEndpoint:
    def test_bets_returns_list(self):
        response = client.get("/api/bets")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_bet_stats_returns_dict(self):
        response = client.get("/api/bets/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "wins" in data
        assert "win_rate" in data


class TestPredictionsEndpoint:
    def test_predictions_returns_list(self):
        response = client.get("/api/predictions")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestConfigEndpoint:
    def test_config_returns_safe_config(self):
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "trading" in data
        # Should NOT expose private keys
        assert "polymarket" not in data or "private_key" not in data.get("polymarket", {})
