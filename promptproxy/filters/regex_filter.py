"""Regex substitution filter."""

import re
from typing import List, Dict, Any

from ..types import FilterContext, FilterResult
from .base import BaseFilter

class RegexFilter(BaseFilter):
    def __init__(self, config):
        super().__init__(config)
        self.rules = []
        for rule in config.rules or []:
            compiled = re.compile(rule["pattern"], re.IGNORECASE)
            self.rules.append({
                "name": rule["name"],
                "pattern": compiled,
                "replacement": rule["replacement"]
            })

    async def apply(self, text: str, context: FilterContext) -> FilterResult:
        original_text = text
        changed = False
        applied_rules = []

        for rule in self.rules:
            if rule["pattern"].search(text):
                text = rule["pattern"].sub(rule["replacement"], text)
                applied_rules.append(rule["name"])
                changed = True

        if changed:
            return FilterResult(
                text=text,
                changed=True,
                action="modify",
                reason=f"Applied rules: {', '.join(applied_rules)}",
                metadata={"applied_rules": applied_rules}
            )
        else:
            return FilterResult(
                text=text,
                changed=False,
                action="pass",
                reason="No rules matched",
                metadata={}
            )