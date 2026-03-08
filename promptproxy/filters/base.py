"""Base filter interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from ..types import FilterContext, FilterResult, FilterableMessage, MessageFilterResult

class BaseFilter(ABC):
    """Common ancestor for all filters (request or response).
    
    Filters can operate in two modes:
    1. Legacy text mode: apply(text, context) - works on a single string
    2. Message mode: apply_messages(messages, context) - preserves message structure
    
    New filters should prefer message mode to maintain conversation context.
    """
    def __init__(self, config):
        self.config = config
        self.name = config.name

    @abstractmethod
    async def apply(self, text: str, context: FilterContext) -> FilterResult:
        """Apply the filter to plain text. For requests the input is the prompt text; 
        for responses it's the raw text returned by the backend."""
        pass
    
    async def apply_messages(
        self, 
        messages: List[FilterableMessage], 
        context: FilterContext
    ) -> MessageFilterResult:
        """Apply the filter to a list of messages while preserving structure.
        
        Default implementation converts to text, applies filter, and rebuilds.
        Override this for filters that need to understand message structure.
        
        Policy: By default, filters only operate on 'user' messages.
        System, assistant, and tool messages are preserved unchanged.
        
        Args:
            messages: List of FilterableMessage objects
            context: Filter context with correlation ID and config
            
        Returns:
            MessageFilterResult with transformed messages
        """
        # Default: delegate to legacy apply() for backward compatibility
        # Only filter user messages by default (conservative policy)
        filtered_messages = []
        any_changed = False
        applied_filters = []
        
        for msg in messages:
            if msg.role == "user":
                # Concatenate all segment contents for filtering
                combined_text = msg.get_transformed_content()
                result = await self.apply(combined_text, context)
                
                if result.action == "reject":
                    return MessageFilterResult(
                        messages=messages,  # Return original on reject
                        changed=False,
                        action="reject",
                        reason=result.reason,
                        metadata={"filter": self.name}
                    )
                
                if result.changed:
                    # Update segments with transformed content
                    new_segments = []
                    for seg in msg.segments:
                        seg.transformed = result.text
                        seg.changed = True
                        new_segments.append(seg)
                    msg.segments = new_segments
                    any_changed = True
                    applied_filters.append(self.name)
            
            # Always preserve non-user messages unchanged
            filtered_messages.append(msg)
        
        return MessageFilterResult(
            messages=filtered_messages,
            changed=any_changed,
            action="modify" if any_changed else "pass",
            reason=f"Filter {self.name} applied" if applied_filters else "No changes",
            metadata={"filters_applied": applied_filters} if applied_filters else {}
        )


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