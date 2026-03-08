"""Filter implementations."""

from .base import BaseFilter
from .semantic_filter import SemanticFilter
from .regex_filter import RegexFilter
from .denylist_filter import DenylistFilter
from .intercept_filter import InterceptFilter
from .noop_filter import NoopFilter

def register_filters():
    from ..registry import register_filter
    register_filter("semantic_filter", SemanticFilter)
    register_filter("regex_filter", RegexFilter)
    register_filter("denylist_filter", DenylistFilter)
    register_filter("intercept_filter", InterceptFilter)
    # response-side placeholder filter
    register_filter("noop_filter", NoopFilter)