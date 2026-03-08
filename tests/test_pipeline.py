import pytest
from unittest.mock import patch
from promptproxy.config import Config
from promptproxy.pipeline import Pipeline, FilterContext
from promptproxy.filters.base import ResponseFilter
from promptproxy.types import FilterResult

@pytest.mark.asyncio
async def test_pipeline_pass():
    config = Config()
    pipeline = Pipeline(config)

    # old `process` method is still an alias for request stage
    result = await pipeline.process("Hello world", "test-id")
    assert result.action == "pass"
    assert result.text == "Hello world"

    # explicit request stage should give same result
    req_result = await pipeline.process_request("Hello world", "test-id")
    assert req_result.action == "pass"
    assert req_result.text == "Hello world"

    # response stage with no filters should also pass through
    resp_result = await pipeline.process_response("OK", "test-id")
    assert resp_result.action == "pass"
    assert resp_result.text == "OK"

@pytest.mark.asyncio
async def test_pipeline_with_filters():
    from promptproxy.filters import register_filters
    register_filters()
    config = Config(request_filters=[
        {"name": "test_filter", "enabled": True}
    ])
    # Mock request filter
    from promptproxy.filters.base import BaseFilter

    class TestFilter(BaseFilter):
        async def apply(self, text, context):
            return FilterResult(text="modified", changed=True, action="modify", reason="test", metadata={})

    from promptproxy.registry import register_filter
    register_filter("test_filter", TestFilter)

    pipeline = Pipeline(config)
    result = await pipeline.process_request("original", "test-id")
    assert result.changed is True
    assert result.text == "modified"

    # ordering test: first filter appends "1", second appends "2"
    class Order1(BaseFilter):
        async def apply(self, text, context):
            return FilterResult(text=text + "1", changed=True, action="modify", reason="first", metadata={})
    class Order2(BaseFilter):
        async def apply(self, text, context):
            return FilterResult(text=text + "2", changed=True, action="modify", reason="second", metadata={})
    register_filter("order1", Order1)
    register_filter("order2", Order2)
    cfg2 = Config(request_filters=[
        {"name": "order1", "enabled": True},
        {"name": "order2", "enabled": True},
    ])
    pl2 = Pipeline(cfg2)
    ord_res = await pl2.process_request("x", "test-id")
    assert ord_res.text == "x12"

    # also verify response stage can handle a simple response filter
    class TestResp(ResponseFilter):
        async def apply(self, text, context):
            return FilterResult(text=text + "!", changed=True, action="modify", reason="resp test", metadata={})
    register_filter("resp_test", TestResp)
    config = Config(response_filters=[{"name": "resp_test", "enabled": True}])
    pipeline = Pipeline(config)
    resp_result = await pipeline.process_response("OK", "test-id")
    assert resp_result.changed is True
    assert resp_result.text == "OK!"

    # if a filter rejects, the action should be propagated
    class RejectResp(ResponseFilter):
        async def apply(self, text, context):
            return FilterResult(text=text, changed=False, action="reject", reason="nope", metadata={})
    register_filter("reject_resp", RejectResp)
    config = Config(response_filters=[{"name": "reject_resp", "enabled": True}])
    pipeline = Pipeline(config)
    rej = await pipeline.process_response("foo", "test-id")
    assert rej.action == "reject"
    assert rej.reason == "nope"

@pytest.mark.asyncio
async def test_semantic_filter_missing_model_fail_open(caplog):
    """Test that semantic filter with missing model fails open through the pipeline."""
    from promptproxy.filters import register_filters
    register_filters()
    config = Config(fail_open=True, request_filters=[
        {"name": "semantic_filter", "enabled": True, "entities": ["PERSON"]}
    ])
    
    with patch('promptproxy.filters.semantic_filter.check_spacy_model', return_value=False):
        pipeline = Pipeline(config)
        # Filter is created (lazy loading), error will occur at apply time
        assert len(pipeline.request_filters) == 1
        
        # Now test that the pipeline handles the error gracefully with fail_open
        result = await pipeline.process_request("test text", "test-id")
        # With fail_open, it should pass through unchanged
        assert result.action == "pass"

@pytest.mark.asyncio
async def test_semantic_filter_missing_model_fail_closed():
    """Test that semantic filter with missing model fails closed at apply time."""
    from promptproxy.filters import register_filters
    from promptproxy.types import FilterContext
    register_filters()
    config = Config(fail_open=False, request_filters=[
        {"name": "semantic_filter", "enabled": True, "entities": ["PERSON"]}
    ])
    
    with patch('promptproxy.filters.semantic_filter.check_spacy_model', return_value=False):
        pipeline = Pipeline(config)
        # Filter is created (lazy loading), error will occur at apply time
        assert len(pipeline.request_filters) == 1
        
        # Now test that apply() raises RuntimeError
        context = FilterContext("test-id", config)
        with pytest.raises(RuntimeError, match="spaCy model"):
            await pipeline.request_filters[0].apply("test text", context)