"""Base filter interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any

from ..types import FilterContext, FilterResult

class BaseFilter(ABC):
    def __init__(self, config):
        self.config = config
        self.name = config.name

    @abstractmethod
    async def apply(self, text: str, context: FilterContext) -> FilterResult:
        """Apply the filter to the text."""
        pass