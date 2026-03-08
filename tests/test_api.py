"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from promptproxy.app import app
from promptproxy.config import Config

def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_chat_completions():
    # Initialize app with config
    from promptproxy.app import init_app
    config = Config()
    init_app(config)

    client = TestClient(app)
    payload = {
        "model": "test",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "choices" in data