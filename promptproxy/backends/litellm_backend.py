"""LiteLLM backend."""

import litellm
from typing import List, Dict, Any

from ..models import Message
from .base import BaseBackend

class LiteLLMBackend(BaseBackend):
    async def generate(self, messages: List[Message], model: str, options: Dict[str, Any]) -> Dict[str, Any]:
        # Convert messages to LiteLLM format
        msgs = [{"role": msg.role, "content": msg.content} for msg in messages]

        # Call LiteLLM
        response = await litellm.acompletion(
            model=model,
            messages=msgs,
            **options
        )

        return {
            "content": response.choices[0].message.content
        }