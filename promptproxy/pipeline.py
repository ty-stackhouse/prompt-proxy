"""Filter pipeline processing."""

from typing import List, Dict, Any
from dataclasses import dataclass

from .config import Config
from .registry import get_filter
from .models import Message
from .types import (
    FilterContext, 
    FilterResult, 
    FilterableMessage, 
    MessageFilterResult
)
import logging

logger = logging.getLogger(__name__)


def messages_to_filterable(messages: List[Message]) -> List[FilterableMessage]:
    """Convert OpenAI Message objects to FilterableMessage for filtering.
    
    This preserves the full message structure (role, content, name) while
    preparing content for filtering.
    
    Policy: All message roles are preserved. Filters operate selectively
    based on their own policies (default: user messages only).
    """
    return [
        FilterableMessage(
            role=msg.role,
            content=msg.content,
            name=msg.name
        )
        for msg in messages
    ]


def filterable_to_messages(filterable_messages: List[FilterableMessage]) -> List[Message]:
    """Convert FilterableMessage objects back to Message for backend forwarding.
    
    This rebuilds the message list from filtered content, preserving the
    original structure (roles, names) while using transformed content.
    """
    return [
        Message(
            role=fm.role,
            content=fm.get_transformed_content(),
            name=fm.name
        )
        for fm in filterable_messages
    ]


class Pipeline:
    """Filter pipeline that processes requests while preserving message structure."""
    
    def __init__(self, config: Config):
        self.config = config
        # initialize request and response filter lists separately
        self.request_filters = self._init_filters(config.request_filters, stage="request")
        self.response_filters = self._init_filters(config.response_filters, stage="response")

    def _init_filters(self, filter_configs, stage: str):
        initialized = []
        for filter_config in filter_configs:
            if filter_config.enabled:
                try:
                    filter_instance = get_filter(filter_config.name, filter_config)
                    if filter_instance is None:
                        raise RuntimeError(f"Unknown filter '{filter_config.name}'")
                    initialized.append(filter_instance)
                    # Log at debug level - filter initialization is internal detail
                    logger.debug(f"{stage.capitalize()} filter {filter_config.name}: enabled")
                except Exception as e:
                    if self.config.fail_open:
                        logger.warning(f"{stage.capitalize()} filter {filter_config.name}: disabled due to error - {e}")
                    else:
                        logger.error(f"{stage.capitalize()} filter {filter_config.name}: failed to initialize - {e}")
                        raise
        return initialized

    async def process_request_messages(
        self, 
        messages: List[Message], 
        correlation_id: str
    ) -> MessageFilterResult:
        """Process a list of messages while preserving structure.
        
        This is the primary entry point for request filtering. It:
        1. Converts messages to filterable format
        2. Runs each filter's apply_messages() method
        3. Rebuilds the message list from transformed content
        4. Returns the result with full message structure preserved
        
        Args:
            messages: Original OpenAI message list
            correlation_id: Request ID for logging/tracing
            
        Returns:
            MessageFilterResult with transformed messages and metadata
        """
        context = FilterContext(correlation_id, self.config)
        
        # Convert to filterable format
        filterable_messages = messages_to_filterable(messages)
        # Log at debug level - pipeline start is internal detail
        logger.debug(
            f"[{correlation_id}] Starting request filter pipeline on {len(filterable_messages)} messages",
            extra={"correlation_id": correlation_id}
        )
        
        # Track all applied filters for metadata
        all_applied_filters: List[str] = []
        current_messages = filterable_messages
        
        for idx, filter_instance in enumerate(self.request_filters, start=1):
            try:
                result = await filter_instance.apply_messages(current_messages, context)
                # Log filter application at debug level - internal detail
                logger.debug(
                    f"[{correlation_id}] [request] Filter {idx}/{len(self.request_filters)} "
                    f"{filter_instance.name}: {result.action} - {result.reason}",
                    extra={"correlation_id": correlation_id}
                )
                
                if result.action == "reject":
                    # Convert back to original message format for error response
                    return MessageFilterResult(
                        messages=messages,  # Return original on reject
                        changed=False,
                        action="reject",
                        reason=result.reason,
                        metadata={"filter": filter_instance.name}
                    )
                
                if result.changed:
                    current_messages = result.messages
                    all_applied_filters.append(filter_instance.name)
                    
            except Exception as e:
                if self.config.fail_open:
                    logger.warning(
                        f"[{correlation_id}] [request] Filter {filter_instance.name} failed, failing open: {e}",
                        extra={"correlation_id": correlation_id}
                    )
                else:
                    logger.error(
                        f"[{correlation_id}] [request] Filter {filter_instance.name} failed, rejecting: {e}",
                        extra={"correlation_id": correlation_id}
                    )
                    return MessageFilterResult(
                        messages=messages,
                        changed=False,
                        action="reject",
                        reason=f"Filter error: {e}",
                        metadata={"filter": filter_instance.name, "error": str(e)}
                    )

        # Log completion at debug level - internal detail
        logger.debug(
            f"[{correlation_id}] Request filtering complete",
            extra={"correlation_id": correlation_id}
        )
        
        return MessageFilterResult(
            messages=current_messages,
            changed=len(all_applied_filters) > 0,
            action="modify" if all_applied_filters else "pass",
            reason="Request filters completed",
            metadata={"filters_applied": all_applied_filters}
        )

    async def process_request(self, text: str, correlation_id: str) -> FilterResult:
        """Run the request filtering stage and return a FilterResult.

        This is the legacy method for backward compatibility. It combines
        all user message content into a single string for filtering.
        
        Note: For new code, prefer process_request_messages() to preserve
        message structure.

        1. Filters are applied in order.
        2. Each receives the text returned by the previous filter.
        3. A reject action short‑circuits and is immediately returned.
        4. Fail‑open behaviour is respected according to configuration.
        """
        context = FilterContext(correlation_id, self.config)
        current_text = text
        overall_changed = False

        # Log at debug level - internal detail
        logger.debug(f"[{correlation_id}] Starting request filter pipeline",
                    extra={"correlation_id": correlation_id})
        for idx, filter_instance in enumerate(self.request_filters, start=1):
            try:
                result = await filter_instance.apply(current_text, context)
                # Log at debug level - internal detail
                logger.debug(
                    f"[{correlation_id}] [request] Filter {idx}/{len(self.request_filters)} "
                    f"{filter_instance.name}: {result.action} - {result.reason}",
                    extra={"correlation_id": correlation_id}
                )
                if result.action == "reject":
                    return result
                if result.changed:
                    current_text = result.text
                    overall_changed = True
            except Exception as e:
                if self.config.fail_open:
                    logger.warning(
                        f"[{correlation_id}] [request] Filter {filter_instance.name} failed, failing open: {e}",
                        extra={"correlation_id": correlation_id}
                    )
                else:
                    logger.error(
                        f"[{correlation_id}] [request] Filter {filter_instance.name} failed, rejecting: {e}",
                        extra={"correlation_id": correlation_id}
                    )
                    return FilterResult(
                        text=current_text,
                        changed=overall_changed,
                        action="reject",
                        reason=f"Filter error: {e}",
                        metadata={}
                    )

        # Log at debug level - internal detail
        logger.debug(f"[{correlation_id}] Request filtering complete",
                    extra={"correlation_id": correlation_id})
        return FilterResult(
            text=current_text,
            changed=overall_changed,
            action="pass",
            reason="All request filters passed",
            metadata={}
        )

    async def process_response(self, text: str, correlation_id: str) -> FilterResult:
        """Run the response filtering stage (currently a no-op placeholder)."""
        context = FilterContext(correlation_id, self.config)
        current_text = text
        overall_changed = False

        # Log at debug level - internal detail
        logger.debug(f"[{correlation_id}] Starting response filter pipeline",
                    extra={"correlation_id": correlation_id})
        for idx, filter_instance in enumerate(self.response_filters, start=1):
            try:
                result = await filter_instance.apply(current_text, context)
                # Log at debug level - internal detail
                logger.debug(
                    f"[{correlation_id}] [response] Filter {idx}/{len(self.response_filters)} "
                    f"{filter_instance.name}: {result.action} - {result.reason}",
                    extra={"correlation_id": correlation_id}
                )
                if result.action == "reject":
                    # propagate reject to caller so that logs/tests can observe it
                    # Keep this at warning level since rejection is significant
                    logger.warning(
                        f"[{correlation_id}] Response rejected by filter {filter_instance.name}: {result.reason}",
                        extra={"correlation_id": correlation_id}
                    )
                    return result
                if result.changed:
                    current_text = result.text
                    overall_changed = True
            except Exception as e:
                if self.config.fail_open:
                    logger.warning(
                        f"[{correlation_id}] [response] Filter {filter_instance.name} failed, failing open: {e}",
                        extra={"correlation_id": correlation_id}
                    )
                else:
                    logger.error(
                        f"[{correlation_id}] [response] Filter {filter_instance.name} failed, logging error: {e}",
                        extra={"correlation_id": correlation_id}
                    )
                    # response stage does not reject the entire request,
                    # we simply continue/fail-open
        # Log at debug level - internal detail
        logger.debug(f"[{correlation_id}] Response filtering complete",
                    extra={"correlation_id": correlation_id})
        return FilterResult(
            text=current_text,
            changed=overall_changed,
            action="pass",
            reason="All response filters passed",
            metadata={}
        )

    # backwards compatibility
    process = process_request
