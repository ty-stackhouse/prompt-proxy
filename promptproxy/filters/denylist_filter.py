"""Denylist filter for policy enforcement."""

from typing import List, Dict, Any

from ..types import FilterContext, FilterResult
from .base import BaseFilter

class DenylistFilter(BaseFilter):
    def __init__(self, config):
        super().__init__(config)
        self.rules = config.rules or []

    async def apply(self, text: str, context: FilterContext) -> FilterResult:
        for rule in self.rules:
            phrase = rule["phrase"]
            if phrase.lower() in text.lower():
                action = rule["action"]
                if action == "reject":
                    return FilterResult(
                        text=text,
                        changed=False,
                        action="reject",
                        reason=rule.get("message", f"Phrase '{phrase}' is not allowed"),
                        metadata={"matched_phrase": phrase}
                    )
                elif action == "replace":
                    replacement = rule.get("replacement", "[FILTERED]")
                    text = text.replace(phrase, replacement)
                    return FilterResult(
                        text=text,
                        changed=True,
                        action="modify",
                        reason=f"Replaced phrase '{phrase}'",
                        metadata={"matched_phrase": phrase}
                    )

        return FilterResult(
            text=text,
            changed=False,
            action="pass",
            reason="No denylist matches",
            metadata={}
        )