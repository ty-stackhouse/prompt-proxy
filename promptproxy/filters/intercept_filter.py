"""Intercept filter stub for future interactive editing."""

from ..types import FilterContext, FilterResult
from .base import BaseFilter

class InterceptFilter(BaseFilter):
    async def apply(self, text: str, context: FilterContext) -> FilterResult:
        # Stub implementation: always pass through
        # Future: pause for user review and editing
        return FilterResult(
            text=text,
            changed=False,
            action="pass",
            reason="Intercept filter disabled",
            metadata={}
        )