"""Filter registry."""

from typing import Dict, Any, Optional
from .filters.base import BaseFilter

FILTER_REGISTRY: Dict[str, type] = {}

def register_filter(name: str, filter_class: type):
    FILTER_REGISTRY[name] = filter_class

def get_filter(name: str, config: Any) -> Optional[BaseFilter]:
    filter_class = FILTER_REGISTRY.get(name)
    if filter_class:
        return filter_class(config)
    return None