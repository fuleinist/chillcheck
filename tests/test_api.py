"""Tests for the JSON API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from chillcheck.api import app


@pytest.fixture
def client(monkeypatch, fake_fetch):
    monkeypatch.setattr("chillcheck.report.fetch_daily", fake_fetch)
    return TestClient(app)


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_assess_endpoint(client):
    response = client.get("/api/assess", params={"lat": -33.78, "lon": 151.12, "years": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["location"]["latitude"] == -33.78
    assert body["varieties"]


def test_assess_rejects_bad_latitude(client):
    response = client.get("/api/assess", params={"lat": 999, "lon": 151.12})
    assert response.status_code == 422


def test_assess_requires_coordinates(client):
    response = client.get("/api/assess")
    assert response.status_code == 422


def test_index_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "chillcheck" in response.text