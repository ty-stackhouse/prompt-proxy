"""Console output renderer for human-facing request display.

This module provides a dedicated stdout presentation layer, separate from the 
logging system. It handles rendering of request input/output to stdout in a 
clean, readable format.

Stdout Contract
==============
- Reserved for product display only (request input/output summaries)
- No JSON, no framework chatter, no stack traces
- Format is compact and professional

Input/Output Definition
========================
- "input request" = the original filterable request content before request filters run
- "output request" = the final request content after all request filters complete
- Only shows relevant filterable text (user messages by default)
- Multiple messages are rendered clearly (e.g., "system: ...", "user: ...")

Security Considerations
======================
Displaying request bodies on stdout can expose sensitive text. This renderer:
- Is disabled by default for normal operation
- Can be enabled via config option
- Truncates long requests to avoid terminal spam
- Fails safely (won't break request handling if stdout fails)
"""

import sys
from typing import List, Optional
from dataclasses import dataclass

from .models import Message
from .types import MessageFilterResult


# Default truncation length for request text display
DEFAULT_MAX_DISPLAY_LENGTH = 500


@dataclass
class RequestDisplay:
    """A single request display with input and output."""
    correlation_id: str
    action: str  # "pass", "modify", "reject"
    filters: List[str]  # List of filter names that acted on the request
    input_text: str  # Original request text (human-readable)
    output_text: str  # Transformed request text (human-readable)
    
    def format(self) -> str:
        """Format as human-readable stdout block."""
        # Action line with correlation ID
        if self.action == "pass":
            action_line = f"[{self.correlation_id[:8]}] PASS"
        elif self.action == "modify":
            filters_str = ", ".join(self.filters) if self.filters else "unknown"
            action_line = f"[{self.correlation_id[:8]}] MODIFY ({filters_str})"
        else:  # reject
            filters_str = ", ".join(self.filters) if self.filters else "unknown"
            action_line = f"[{self.correlation_id[:8]}] REJECT ({filters_str})"
        
        # Input/output lines
        input_line = f"input request:  {self.input_text}"
        
        if self.action == "reject":
            output_line = "output request: <blocked>"
        else:
            output_line = f"output request: {self.output_text}"
        
        return "\n".join([action_line, input_line, output_line])


def _truncate_text(text: str, max_length: int = DEFAULT_MAX_DISPLAY_LENGTH) -> str:
    """Truncate text to max length, adding ellipsis if truncated."""
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + "..."


def _render_messages(messages: List[Message]) -> str:
    """Render a list of messages as human-readable text.
    
    Shows only filterable messages (user) by default, with role prefix.
    System and assistant messages are shown with their role for context.
    """
    lines = []
    for msg in messages:
        content = _truncate_text(msg.content)
        if msg.role == "system":
            lines.append(f"system: {content}")
        elif msg.role == "user":
            lines.append(f"user: {content}")
        elif msg.role == "assistant":
            lines.append(f"assistant: {content}")
        else:
            lines.append(f"{msg.role}: {content}")
    
    return "\n".join(lines)


def _render_filterable_messages(messages: List[Message]) -> str:
    """Render only the filterable message content (user messages).
    
    This is the primary content that filters operate on.
    """
    user_messages = [msg for msg in messages if msg.role == "user"]
    
    if not user_messages:
        return "<no user messages>"
    
    lines = []
    for msg in user_messages:
        content = _truncate_text(msg.content)
        lines.append(content)
    
    return "\n".join(lines)


def render_request(
    correlation_id: str,
    original_messages: List[Message],
    filter_result: MessageFilterResult,
    max_length: int = DEFAULT_MAX_DISPLAY_LENGTH,
    enabled: bool = True
) -> Optional[str]:
    """Render request input/output to stdout.
    
    This is the main entry point for rendering request display.
    It shows the original request before filters and the final 
    request after all filters have run.
    
    Args:
        correlation_id: Request ID for display
        original_messages: Original messages before filtering
        filter_result: Result from the pipeline containing filtered messages
        max_length: Maximum display length for request text
        enabled: Whether to actually render (allows toggling via config)
    
    Returns:
        Formatted string if enabled, None otherwise
    """
    if not enabled:
        return None
    
    try:
        # Determine action based on filter result
        action = filter_result.action
        
        # Collect filters that were applied
        filters = filter_result.metadata.get("filters_applied", [])
        
        # Render input (original request before filters)
        input_text = _render_filterable_messages(original_messages)
        
        # Render output (after filters)
        if action == "reject":
            output_text = "<blocked>"
        else:
            output_text = _render_filterable_messages(filter_result.messages)
        
        display = RequestDisplay(
            correlation_id=correlation_id,
            action=action,
            filters=filters,
            input_text=input_text,
            output_text=output_text
        )
        
        return display.format()
        
    except Exception as e:
        # Fail safely - never break request handling due to display issues
        # Write error to stderr as a warning
        import warnings
        warnings.warn(f"Console render failed: {e}")
        return None


def print_request(
    correlation_id: str,
    original_messages: List[Message],
    filter_result: MessageFilterResult,
    max_length: int = DEFAULT_MAX_DISPLAY_LENGTH,
    enabled: bool = True
):
    """Render and print request display to stdout.
    
    This is a convenience wrapper that prints directly to stdout.
    """
    output = render_request(
        correlation_id=correlation_id,
        original_messages=original_messages,
        filter_result=filter_result,
        max_length=max_length,
        enabled=enabled
    )
    
    if output:
        try:
            print(output)
        except Exception:
            # Fail safely - don't let stdout issues affect requests
            pass
