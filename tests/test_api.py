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


def test_response_filter_integration():
    # register a simple response filter and ensure it modifies output content
    from promptproxy.filters import register_filters
    from promptproxy.filters.base import ResponseFilter
    from promptproxy.types import FilterResult
    from promptproxy.registry import register_filter

    register_filters()

    class AppendFilter(ResponseFilter):
        async def apply(self, text, context):
            return FilterResult(text=text + "_X", changed=True, action="modify", reason="append", metadata={})

    register_filter("append_filter", AppendFilter)

    from promptproxy.app import init_app
    cfg = Config(response_filters=[{"name": "append_filter", "enabled": True}])
    init_app(cfg)
    client = TestClient(app)
    payload = {"model": "test", "messages": [{"role": "user", "content": "Hello"}]}
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    assert content.endswith("_X")


def test_check_prerequisites_semantic_warn(caplog, monkeypatch):
    """Test that semantic filter warning is handled during filter initialization."""
    from promptproxy.filters import register_filters
    from promptproxy.pipeline import Pipeline
    from unittest.mock import patch
    register_filters()
    cfg = Config(fail_open=True, request_filters=[{"name": "semantic_filter", "enabled": True}])
    
    # simulate missing model - filter is created but will fail when apply() is called
    with patch('promptproxy.filters.semantic_filter.check_spacy_model', return_value=False):
        pipeline = Pipeline(cfg)
        # Filter is created (lazy loading), error will occur at apply time
        assert len(pipeline.request_filters) == 1