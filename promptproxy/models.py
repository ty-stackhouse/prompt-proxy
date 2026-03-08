"""Pydantic models for API requests and responses.

These models are designed to be intentionally OpenAI-compatible for the subset
of the API that PromptProxy supports.

Supported endpoints:
- POST /v1/chat/completions (subset of OpenAI Chat API)
- GET /v1/models (static list)
- GET /health

Unsupported fields are ignored gracefully where reasonable.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class MessageRole(str, Enum):
    """Supported message roles matching OpenAI API."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"


class Message(BaseModel):
    """OpenAI-compatible message format.
    
    Required fields: role, content
    Optional fields: name, function_call (for responses)
    """
    role: str
    content: str
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request.
    
    This is a subset of the full OpenAI API. Only supported fields are
    validated; others are ignored if present.
    
    Supported fields:
    - model (required): Model identifier
    - messages (required): List of message objects
    - temperature: Sampling temperature (0-2)
    - max_tokens: Maximum tokens to generate
    - top_p: Nucleus sampling parameter
    - n: Number of completions to generate
    - stop: Stop sequences
    - stream: Streaming response (not yet supported, ignored)
    - presence_penalty: Presence penalty
    - frequency_penalty: Frequency penalty
    - user: User identifier for tracking
    
    Unsupported (ignored):
    - functions, function_call: Function calling (future)
    - logit_bias: Logit bias (future)
    """
    model: str
    messages: List[Message]
    temperature: Optional[float] = Field(default=1.0, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=1000, ge=1)
    top_p: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    n: Optional[int] = Field(default=1, ge=1)
    stop: Optional[List[str]] = None
    stream: Optional[bool] = False
    presence_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    user: Optional[str] = None
    
    # Unsupported fields - accepted but ignored
    # functions: Optional[List[Dict[str, Any]]] = None
    # function_call: Optional[str] = None
    # logit_bias: Optional[Dict[str, float]] = None


class Usage(BaseModel):
    """OpenAI-compatible usage statistics."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatMessage(BaseModel):
    """Message in a chat completion choice."""
    role: str
    content: str
    name: Optional[str] = None


class ChatCompletionChoice(BaseModel):
    """OpenAI-compatible chat completion choice."""
    index: int
    message: ChatMessage
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response.
    
    This follows the OpenAI Chat API response format.
    """
    id: str = Field(description="Unique identifier for this completion")
    object: str = Field(default="chat.completion", description="Object type")
    created: int = Field(description="Unix timestamp of creation")
    model: str = Field(description="Model used for completion")
    choices: List[ChatCompletionChoice] = Field(
        description="List of completion choices"
    )
    usage: Usage = Field(description="Token usage statistics")
    
    # Optional fields from OpenAI API
    system_fingerprint: Optional[str] = None


class Model(BaseModel):
    """OpenAI-compatible model representation for /v1/models."""
    id: str
    object: str = "model"
    created: int
    owned_by: str
    permission: List[Dict[str, Any]] = Field(default_factory=list)
    root: str
    parent_model: Optional[str] = None


class ModelList(BaseModel):
    """OpenAI-compatible model list response."""
    object: str = "list"
    data: List[Model]