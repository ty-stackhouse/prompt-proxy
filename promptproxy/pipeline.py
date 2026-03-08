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
        self.filters = []
        for filter_config in config.filters:
            if filter_config.enabled:
                try:
                    filter_instance = get_filter(filter_config.name, filter_config)
                    self.filters.append(filter_instance)
                    logger.info(f"Filter {filter_config.name}: enabled")
                except Exception as e:
                    if config.fail_open:
                        logger.warning(f"Filter {filter_config.name}: disabled due to error - {e}")
                    else:
                        logger.error(f"Filter {filter_config.name}: failed to initialize - {e}")
                        raise

    async def process(self, text: str, correlation_id: str) -> FilterResult:
        context = FilterContext(correlation_id, self.config)
        current_text = text
        overall_changed = False

        for filter_instance in self.filters:
            try:
                result = await filter_instance.apply(current_text, context)
                logger.info(
                    f"[{correlation_id}] Filter {filter_instance.name}: {result.action} - {result.reason}",
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
                        f"[{correlation_id}] Filter {filter_instance.name} failed, failing open: {e}",
                        extra={"correlation_id": correlation_id}
                    )
                else:
                    logger.error(
                        f"[{correlation_id}] Filter {filter_instance.name} failed, rejecting: {e}",
                        extra={"correlation_id": correlation_id}
                    )
                    return FilterResult(
                        text=current_text,
                        changed=overall_changed,
                        action="reject",
                        reason=f"Filter error: {e}",
                        metadata={}
                    )

        return FilterResult(
            text=current_text,
            changed=overall_changed,
            action="pass",
            reason="All filters passed",
            metadata={}
        )