"""Stub backend for testing."""

from typing import List, Dict, Any

from ..models import Message
from .base import BaseBackend

class StubBackend(BaseBackend):
    async def generate(self, messages: List[Message], model: str, options: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "content": "I am a stub backend. Your request was received and processed by PromptProxy."
        }