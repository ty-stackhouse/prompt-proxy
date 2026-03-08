"""A no-op filter used to scaffold the response filter stage.

This filter is registered so that users can reference it in the
`response_filters` section of their configuration; by default it does
nothing and is disabled.
"""

from ..types import FilterContext, FilterResult
from .base import ResponseFilter


class NoopFilter(ResponseFilter):
    def __init__(self, config):
        super().__init__(config)

    async def apply(self, text: str, context: FilterContext) -> FilterResult:
        # simply return the input untouched
        return FilterResult(
            text=text,
            changed=False,
            action="pass",
            reason="noop",
            metadata={}
        )
