"""Tests for filters."""

import pytest
from promptproxy.filters.regex_filter import RegexFilter
from promptproxy.filters.denylist_filter import DenylistFilter
from promptproxy.pipeline import FilterContext
from promptproxy.config import Config

@pytest.mark.asyncio
async def test_regex_filter():
    config = type('Config', (), {
        'name': 'regex_filter',
        'rules': [
            {'name': 'test', 'pattern': r'bad', 'replacement': 'good'}
        ]
    })()
    filter_instance = RegexFilter(config)
    context = FilterContext("test", Config())

    result = await filter_instance.apply("This is bad", context)
    assert result.changed is True
    assert "good" in result.text

@pytest.mark.asyncio
async def test_denylist_filter_reject():
    config = type('Config', (), {
        'name': 'denylist_filter',
        'rules': [
            {'phrase': 'bad', 'action': 'reject', 'message': 'Not allowed'}
        ]
    })()
    filter_instance = DenylistFilter(config)
    context = FilterContext("test", Config())

    result = await filter_instance.apply("This is bad", context)
    assert result.action == "reject"