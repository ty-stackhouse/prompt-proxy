"""Base backend interface."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any

from ..models import Message

class BaseBackend(ABC):
    def __init__(self, config):
        self.config = config

    @abstractmethod
    async def generate(self, messages: List[Message], model: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a response from the backend."""
        pass