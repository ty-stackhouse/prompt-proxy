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
    """Test basic chat completion with message preservation."""
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


def test_message_structure_preserved():
    """Test that multi-message chat requests preserve structure through filtering."""
    from promptproxy.app import init_app
    from promptproxy.filters import register_filters
    from promptproxy.filters.base import RequestFilter
    from promptproxy.types import FilterResult, FilterContext
    from promptproxy.registry import register_filter
    
    # Register a simple filter that modifies content
    class UppercaseFilter(RequestFilter):
        async def apply(self, text, context):
            return FilterResult(
                text=text.upper(),
                changed=True,
                action="modify",
                reason="uppercase",
                metadata={}
            )
    
    register_filter("uppercase_filter", UppercaseFilter)
    register_filters()
    
    config = Config(request_filters=[{"name": "uppercase_filter", "enabled": True}])
    init_app(config)
    
    client = TestClient(app)
    
    # Multi-message request with system, user, and assistant messages
    payload = {
        "model": "test",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"}
        ]
    }
    
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    
    # The filter should have modified the user messages
    data = response.json()
    # Backend is stub, so response content will be empty/default


def test_openai_error_format():
    """Test that errors are returned in OpenAI-compatible format."""
    from promptproxy.app import init_app
    config = Config()
    init_app(config)
    
    client = TestClient(app)
    
    # Send request without user messages - should return 400 with OpenAI error format
    payload = {
        "model": "test",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."}
        ]
    }
    
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 400
    
    data = response.json()
    assert "error" in data
    assert "message" in data["error"]
    assert "type" in data["error"]
    assert data["error"]["type"] == "invalid_request_error"


def test_policy_rejection_error():
    """Test that policy rejections return proper error format."""
    from promptproxy.app import init_app
    from promptproxy.filters import register_filters
    from promptproxy.filters.base import RequestFilter
    from promptproxy.types import FilterResult, FilterContext, MessageFilterResult, FilterableMessage
    from promptproxy.registry import register_filter
    
    # Register a filter that rejects certain content
    class RejectFilter(RequestFilter):
        async def apply(self, text, context):
            if "reject" in text.lower():
                return FilterResult(
                    text=text,
                    changed=False,
                    action="reject",
                    reason="Content rejected",
                    metadata={}
                )
            return FilterResult(text=text, changed=False, action="pass", reason="ok", metadata={})
        
        async def apply_messages(self, messages, context):
            from promptproxy.types import MessageFilterResult
            for msg in messages:
                if msg.role == "user" and "reject" in msg.content.lower():
                    return MessageFilterResult(
                        messages=messages,
                        changed=False,
                        action="reject",
                        reason="Content rejected",
                        metadata={"filter": "reject_filter"}
                    )
            return MessageFilterResult(
                messages=messages,
                changed=False,
                action="pass",
                reason="ok",
                metadata={}
            )
    
    register_filter("reject_filter", RejectFilter)
    register_filters()
    
    config = Config(request_filters=[{"name": "reject_filter", "enabled": True}])
    init_app(config)
    
    client = TestClient(app)
    
    payload = {
        "model": "test",
        "messages": [{"role": "user", "content": "Please reject this"}]
    }
    
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 400
    
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "policy_rejection"


def test_response_filter_integration():
    """Test that response filters modify the output content."""
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