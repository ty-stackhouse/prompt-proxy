"""Backend implementations."""

from ..config import Config
from .base import BaseBackend
from .stub import StubBackend
from .litellm_backend import LiteLLMBackend

def get_backend(config: Config) -> BaseBackend:
    if config.backend.type == "stub":
        return StubBackend(config)
    elif config.backend.type == "litellm":
        return LiteLLMBackend(config)
    else:
        raise ValueError(f"Unknown backend type: {config.backend.type}")