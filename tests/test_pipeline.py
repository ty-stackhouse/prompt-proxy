import pytest
from unittest.mock import patch
from promptproxy.config import Config
from promptproxy.pipeline import Pipeline, FilterContext

@pytest.mark.asyncio
async def test_pipeline_pass():
    config = Config()
    pipeline = Pipeline(config)

    result = await pipeline.process("Hello world", "test-id")
    assert result.action == "pass"
    assert result.text == "Hello world"

@pytest.mark.asyncio
async def test_pipeline_with_filters():
    from promptproxy.filters import register_filters
    register_filters()
    config = Config(filters=[
        {"name": "test_filter", "enabled": True}
    ])
    # Mock filter
    from promptproxy.filters.base import BaseFilter
    from promptproxy.types import FilterResult

    class TestFilter(BaseFilter):
        async def apply(self, text, context):
            return FilterResult(text="modified", changed=True, action="modify", reason="test", metadata={})

    from promptproxy.registry import register_filter
    register_filter("test_filter", TestFilter)

    pipeline = Pipeline(config)
    result = await pipeline.process("original", "test-id")
    assert result.changed == True
    assert result.text == "modified"

def test_semantic_filter_missing_model_fail_open(caplog):
    from promptproxy.filters import register_filters
    register_filters()
    config = Config(fail_open=True, filters=[
        {"name": "semantic_filter", "enabled": True, "entities": ["PERSON"]}
    ])
    
    with patch('promptproxy.filters.semantic_filter.check_spacy_model', return_value=False):
        pipeline = Pipeline(config)
        # Should not raise, and filter should be disabled
        assert len(pipeline.filters) == 0  # Since semantic_filter failed
        assert "disabled due to error" in caplog.text

def test_semantic_filter_missing_model_fail_closed():
    from promptproxy.filters import register_filters
    register_filters()
    config = Config(fail_open=False, filters=[
        {"name": "semantic_filter", "enabled": True, "entities": ["PERSON"]}
    ])
    
    with patch('promptproxy.filters.semantic_filter.check_spacy_model', return_value=False):
        with pytest.raises(RuntimeError, match="spaCy model"):
            Pipeline(config)