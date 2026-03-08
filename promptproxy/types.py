"""Shared types and dataclasses."""

from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class FilterContext:
    correlation_id: str
    config: Any  # Avoid circular import

@dataclass
class FilterResult:
    text: str
    changed: bool
    action: str  # "pass", "modify", "reject"
    reason: str
    metadata: Dict[str, Any]