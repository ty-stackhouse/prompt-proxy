"""Filter pipeline processing."""

from typing import List, Dict, Any
from dataclasses import dataclass

from .config import Config
from .registry import get_filter
import logging
from .types import FilterContext, FilterResult

logger = logging.getLogger(__name__)

class Pipeline:
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
                    logger.info(f"{stage.capitalize()} filter {filter_config.name}: enabled")
                except Exception as e:
                    if self.config.fail_open:
                        logger.warning(f"{stage.capitalize()} filter {filter_config.name}: disabled due to error - {e}")
                    else:
                        logger.error(f"{stage.capitalize()} filter {filter_config.name}: failed to initialize - {e}")
                        raise
        return initialized

    async def process_request(self, text: str, correlation_id: str) -> FilterResult:
        """Run the request filtering stage and return a FilterResult.

        1. Filters are applied in order.
        2. Each receives the text returned by the previous filter.
        3. A reject action short‑circuits and is immediately returned.
        4. Fail‑open behaviour is respected according to configuration.
        """
        context = FilterContext(correlation_id, self.config)
        current_text = text
        overall_changed = False

        logger.info(f"[{correlation_id}] Starting request filter pipeline",
                    extra={"correlation_id": correlation_id})
        for idx, filter_instance in enumerate(self.request_filters, start=1):
            try:
                result = await filter_instance.apply(current_text, context)
                logger.info(
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

        logger.info(f"[{correlation_id}] Request filtering complete",
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

        logger.info(f"[{correlation_id}] Starting response filter pipeline",
                    extra={"correlation_id": correlation_id})
        for idx, filter_instance in enumerate(self.response_filters, start=1):
            try:
                result = await filter_instance.apply(current_text, context)
                logger.info(
                    f"[{correlation_id}] [response] Filter {idx}/{len(self.response_filters)} "
                    f"{filter_instance.name}: {result.action} - {result.reason}",
                    extra={"correlation_id": correlation_id}
                )
                if result.action == "reject":
                    # propagate reject to caller so that logs/tests can observe it
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
        logger.info(f"[{correlation_id}] Response filtering complete",
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
