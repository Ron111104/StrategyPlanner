"""API integration tests using FastAPI TestClient."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestRegimeEndpoints:
    def test_get_regime(self, client):
        resp = client.get("/regime/current")
        assert resp.status_code == 200
        data = resp.json()
        assert "regime" in data
        assert "macro_bias" in data

    def test_update_regime(self, client):
        resp = client.put("/regime/update", json={
            "regime": "trend",
            "macro_bias": "hawkish",
            "notes": "Test update",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["state"]["regime"] == "trend"
        assert data["state"]["macro_bias"] == "hawkish"

    def test_invalid_regime_rejected(self, client):
        resp = client.put("/regime/update", json={
            "regime": "invalid_regime",
            "macro_bias": "neutral",
        })
        assert resp.status_code == 422


class TestAccountEndpoints:
    def test_get_account_config(self, client):
        resp = client.get("/account/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "max_position_lots" in data

    def test_update_account_config(self, client):
        resp = client.put("/account/config", json={
            "max_position_lots": 50,
            "max_risk_per_trade_usd": 25000.0,
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["config"]["max_position_lots"] == 50


class TestMarketDataEndpoints:
    def test_snapshots_empty(self, client):
        resp = client.get("/market-data/snapshots")
        assert resp.status_code == 200
        data = resp.json()
        assert "snapshots" in data
        assert "spreads" in data

    def test_ohlcv_not_found(self, client):
        resp = client.get("/market-data/ohlcv/UNKNOWN/1H")
        assert resp.status_code == 404

    def test_indicators_not_found(self, client):
        resp = client.get("/market-data/indicators/UNKNOWN/1H")
        assert resp.status_code == 404


class TestStrategyEndpoints:
    def test_get_signals_empty(self, client):
        resp = client.get("/strategy/signals")
        assert resp.status_code == 200
        data = resp.json()
        assert "cards" in data

    def test_risk_missing_params(self, client):
        resp = client.get("/strategy/risk/FFN26?direction=long&entry=0&stop=0&target=0&product_key=fed_funds")
        assert resp.status_code == 400


class TestPageRoutes:
    def test_dashboard_page(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Dashboard" in resp.text or "ZQ" in resp.text

    def test_strategy_page(self, client):
        resp = client.get("/strategy")
        assert resp.status_code == 200
        assert "Strategy" in resp.text

    def test_risk_page(self, client):
        resp = client.get("/risk")
        assert resp.status_code == 200
        assert "Risk" in resp.text

    def test_replay_page(self, client):
        resp = client.get("/replay")
        assert resp.status_code == 200
        assert "Replay" in resp.text


class TestOpenAPI:
    def test_openapi_json(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "openapi" in data
        assert "paths" in data

    def test_swagger_ui(self, client):
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_redoc(self, client):
        resp = client.get("/redoc")
        assert resp.status_code == 200
