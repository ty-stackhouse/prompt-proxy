"""Tests for stub backend."""

import pytest
from promptproxy.backends.stub import StubBackend
from promptproxy.config import Config
from promptproxy.models import Message

@pytest.mark.asyncio
async def test_stub_backend():
    config = Config()
    backend = StubBackend(config)

    messages = [Message(role="user", content="test")]
    response = await backend.generate(messages, "model", {})

    assert "stub backend" in response["content"].lower()