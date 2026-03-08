"""Shared types and dataclasses."""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum


class MessageRole(str, Enum):
    """Message roles that can be processed by filters.
    
    Policy: By default, filters operate on 'user' messages only.
    System messages are preserved as-is to maintain context.
    Assistant messages are preserved to maintain conversation history.
    Future roles (tool, etc.) are preserved.
    """
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TOOL = "tool"


@dataclass
class ContentSegment:
    """A text segment within a message that can be filtered.
    
    This is an internal representation for filterable text that preserves
    the original message structure. Filters transform these segments
    while the surrounding message metadata (role, name, etc.) is retained.
    
    Attributes:
        original: The original text content
        transformed: The filtered/transformed text (may equal original)
        changed: Whether transformation occurred
        role: The message role (used for filtering policy)
    """
    original: str
    transformed: str = ""
    changed: bool = False
    role: str = "user"
    
    def __post_init__(self):
        if self.transformed == "":
            self.transformed = self.original


@dataclass
class FilterableMessage:
    """A message with its filterable content segments identified.
    
    This preserves the full OpenAI message structure while allowing
    filters to operate on the content portions.
    
    Attributes:
        role: Message role (system, user, assistant, function, tool)
        content: Original content string
        name: Optional name field
        segments: List of ContentSegment objects for filtering
    """
    role: str
    content: str
    name: Optional[str] = None
    segments: List[ContentSegment] = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize segments from content if not provided."""
        if not self.segments and self.content:
            self.segments = [ContentSegment(
                original=self.content,
                transformed=self.content,
                role=self.role
            )]
    
    def get_transformed_content(self) -> str:
        """Reconstruct content from transformed segments."""
        return "".join(s.transformed for s in self.segments)
    
    def has_changes(self) -> bool:
        """Check if any segment was transformed."""
        return any(s.changed for s in self.segments)


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


@dataclass
class MessageFilterResult:
    """Result of filtering a message list.
    
    Unlike FilterResult which works on plain text, this preserves
    the message structure end-to-end.
    
    Attributes:
        messages: The filtered message list (preserves original structure)
        changed: Whether any message content was modified
        action: "pass", "modify", or "reject"
        reason: Human-readable reason for the result
        metadata: Additional metadata (filters applied, etc.)
    """
    messages: List[FilterableMessage]
    changed: bool
    action: str
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)