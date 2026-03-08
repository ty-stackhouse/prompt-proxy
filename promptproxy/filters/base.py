"""Base filter interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any

from ..types import FilterContext, FilterResult

class BaseFilter(ABC):
    """Common ancestor for all filters (request or response)."""
    def __init__(self, config):
        self.config = config
        self.name = config.name

    @abstractmethod
    async def apply(self, text: str, context: FilterContext) -> FilterResult:
        """Apply the filter.  For requests the input is the prompt text; for
        responses it's the raw text returned by the backend."""
        pass


class RequestFilter(BaseFilter):
    """Marker class for filters that operate on incoming requests.

    Existing filters should inherit from this for clarity.
    """
    pass


class ResponseFilter(BaseFilter):
    """Marker class for filters that operate on backend responses.

    For now the implementation is identical to :class:`BaseFilter`, but the
    separate type makes the two stages explicit and easier to document.
    """
    pass