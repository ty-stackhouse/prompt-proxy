"""FastAPI application for PromptProxy.

OpenAI-compatible local interception proxy.

Supported endpoints:
- POST /v1/chat/completions: Chat completion API (subset)
- GET /v1/models: List available models
- GET /health: Health check
"""

import uuid
import time
from typing import List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import Config, load_config
from .models import (
    ChatCompletionRequest, 
    ChatCompletionResponse, 
    Message,
    Model,
    ModelList,
    Usage,
    ChatCompletionChoice,
    ChatMessage
)
from .pipeline import Pipeline, filterable_to_messages
from .backends import get_backend
from .logging_config import configure_logging, log_demo_summary
from .errors import (
    policy_rejection_error,
    invalid_request_error,
    server_error,
    service_unavailable_error,
    OpenAIErrorType,
    OpenAIErrorCode
)
import logging
from .filters import register_filters

# logger instance (handlers attached when logging is configured)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PromptProxy", 
    version="0.2.0",
    description="OpenAI-compatible local interception proxy for LLM traffic"
)

config: Config = None
pipeline: Pipeline = None
backend = None


def init_app(cfg: Config = None):
    """Initialize the application with configuration.
    
    If no config is provided, loads from default config.yaml.
    Handles port collision detection and missing NLP dependencies gracefully.
    """
    global config, pipeline, backend
    
    # Load config if not provided
    if cfg is None:
        try:
            cfg = load_config()
        except FileNotFoundError:
            # Use default config if no config file exists
            cfg = Config()
        except Exception as e:
            raise RuntimeError(f"Failed to load config: {e}")
    
    config = cfg
    
    # Check for port availability before starting
    _check_port_available(config.server.host, config.server.port)
    
    # configure logging before anything else so that early messages obey settings
    configure_logging(
        level=config.logging.level, 
        file_path=config.logging.file_path,
        demo_mode=config.ui.demo_mode
    )
    
    # Register available filters
    register_filters()
    
    # Initialize pipeline
    pipeline = Pipeline(config)
    
    # Initialize backend
    backend = get_backend(config)
    
    logger.info(
        f"PromptProxy initialized on {config.server.host}:{config.server.port}",
        extra={}
    )


def _check_port_available(host: str, port: int):
    """Check if the port is available and raise friendly error if not."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        sock.close()
    except OSError as e:
        if e.errno == 98:  # Address already in use
            raise RuntimeError(
                f"Port {port} is already in use. "
                f"Stop any running PromptProxy instances or change the port in config.yaml."
            )
        elif e.errno == 13:  # Permission denied
            raise RuntimeError(
                f"Permission denied to bind to port {port}. "
                f"Try using a port above 1024 or run with appropriate permissions."
            )
        else:
            raise RuntimeError(f"Failed to bind to port {port}: {e}")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/v1/models", response_model=ModelList)
async def list_models():
    """List available models.
    
    Returns a static list of models that can be used with /v1/chat/completions.
    In production, this could be dynamically populated based on the backend.
    """
    models = [
        Model(
            id="promptproxy-default",
            object="model",
            created=int(datetime(2024, 1, 1).timestamp()),
            owned_by="promptproxy",
            root="promptproxy-default"
        ),
        Model(
            id="gpt-3.5-turbo",
            object="model",
            created=int(datetime(2023, 6, 1).timestamp()),
            owned_by="openai",
            root="gpt-3.5-turbo"
        ),
        Model(
            id="gpt-4",
            object="model",
            created=int(datetime(2023, 3, 14).timestamp()),
            owned_by="openai",
            root="gpt-4"
        ),
        Model(
            id="gpt-4-turbo",
            object="model",
            created=int(datetime(2023, 11, 6).timestamp()),
            owned_by="openai",
            root="gpt-4-turbo"
        ),
    ]
    return ModelList(data=models)


def _count_tokens(text: str) -> int:
    """Approximate token count (simple word-based estimate)."""
    return len(text.split())


def _extract_filter_metadata(result) -> tuple:
    """Extract filter names and action from pipeline result."""
    filters = result.metadata.get("filters_applied", [])
    action = result.action
    return filters, action


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest, req: Request):
    """Handle chat completion requests.
    
    OpenAI-compatible endpoint. Accepts a subset of the OpenAI Chat API
    and returns responses in OpenAI format.
    
    Request filtering:
    - Runs request filters on user messages while preserving message structure
    - System and assistant messages are preserved unchanged
    - Rejects with policy_rejection error if filter rejects
    
    Response handling:
    - Forwards to backend with full message history
    - Optionally runs response filters
    - Returns OpenAI-style response
    """
    correlation_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Log request start at debug level (not info) to keep terminal clean
    logger.debug(
        f"[{correlation_id}] Request started",
        extra={"correlation_id": correlation_id}
    )

    # Validate: require at least one user message
    user_messages = [msg for msg in request.messages if msg.role == "user"]
    if not user_messages:
        logger.warning(
            f"[{correlation_id}] No user messages found",
            extra={"correlation_id": correlation_id}
        )
        return invalid_request_error(
            message="No user messages found",
            param="messages",
            code="empty_messages"
        )

    # Log message count at debug level
    logger.debug(
        f"[{correlation_id}] Received {len(request.messages)} messages "
        f"({len([m for m in request.messages if m.role == 'user'])} user, "
        f"{len([m for m in request.messages if m.role == 'system'])} system, "
        f"{len([m for m in request.messages if m.role == 'assistant'])} assistant)",
        extra={"correlation_id": correlation_id}
    )

    # Run request-stage filters with message preservation
    try:
        result = await pipeline.process_request_messages(
            request.messages, 
            correlation_id
        )
        
        filters_applied, action = _extract_filter_metadata(result)
        
        if result.action == "reject":
            logger.warning(
                f"[{correlation_id}] Request rejected: {result.reason}",
                extra={"correlation_id": correlation_id}
            )
            return policy_rejection_error(message=f"Policy rejection: {result.reason}")

        # Rebuild message list from filtered content
        filtered_messages = filterable_to_messages(result.messages)
        
        # Log filtering result at debug level
        logger.debug(
            f"[{correlation_id}] Filtering complete: "
            f"{'modified' if result.changed else 'unchanged'}, "
            f"filters: {filters_applied}",
            extra={"correlation_id": correlation_id}
        )
        
        if config.logging.log_raw_prompt:
            # Only log if explicitly enabled (security-sensitive)
            for msg in filtered_messages:
                logger.debug(
                    f"[{correlation_id}] Message [{msg.role}]: {msg.content[:100]}...",
                    extra={"correlation_id": correlation_id}
                )

    except Exception as e:
        if config.fail_open:
            logger.warning(
                f"[{correlation_id}] Request pipeline error, failing open: {e}",
                extra={"correlation_id": correlation_id}
            )
            filtered_messages = request.messages  # Use original messages
            filters_applied = []
            action = "pass"
        else:
            logger.error(
                f"[{correlation_id}] Request pipeline error, rejecting: {e}",
                extra={"correlation_id": correlation_id}
            )
            return server_error(message="Internal processing error")

        # Forward to backend with full message history
    try:
        backend_response = await backend.generate(
            messages=filtered_messages,
            model=request.model,
            options={
                "max_tokens": request.max_tokens, 
                "temperature": request.temperature,
                "top_p": request.top_p,
                "n": request.n,
                "stop": request.stop,
            }
        )
        # Log backend response at debug level
        logger.debug(
            f"[{correlation_id}] Backend response received",
            extra={"correlation_id": correlation_id}
        )
    except Exception as e:
        logger.error(
            f"[{correlation_id}] Backend error: {e}",
            extra={"correlation_id": correlation_id}
        )
        return service_unavailable_error(message=f"Backend error: {str(e)}")

    # Optionally run response-stage filters on the text returned by the backend
    raw_content = backend_response.get("content", "")
    resp_result = await pipeline.process_response(raw_content, correlation_id)
    
    # Log response filter changes at debug level
    if resp_result.changed:
        logger.debug(
            f"[{correlation_id}] Response text modified by filters",
            extra={"correlation_id": correlation_id}
        )
        
    if resp_result.action == "reject":
        # We don't fail the HTTP request, but we log the rejection for observability
        logger.warning(
            f"[{correlation_id}] Response rejected by filter: {resp_result.reason}",
            extra={"correlation_id": correlation_id}
        )
        
    final_content = resp_result.text

    # Calculate token counts (approximate)
    # Use transformed content for prompt tokens
    prompt_tokens = sum(_count_tokens(m.content) for m in filtered_messages)
    completion_tokens = _count_tokens(final_content)
    total_tokens = prompt_tokens + completion_tokens

    # Build OpenAI-style response
    choice = ChatCompletionChoice(
        index=0,
        message=ChatMessage(
            role="assistant",
            content=final_content
        ),
        finish_reason="stop"
    )
    
    usage = Usage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens
    )
    
    response = ChatCompletionResponse(
        id=f"chatcmpl-{correlation_id[:8]}",
        object="chat.completion",
        created=int(datetime.now().timestamp()),
        model=request.model,
        choices=[choice],
        usage=usage
    )

    # Calculate latency
    latency_ms = (time.time() - start_time) * 1000
    
    logger.info(
        f"[{correlation_id}] Request completed in {latency_ms:.0f}ms",
        extra={"correlation_id": correlation_id}
    )
    
    # Emit demo output if in demo mode
    if config.ui.demo_mode:
        log_demo_summary(
            correlation_id=correlation_id,
            action=action,
            filters=filters_applied,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms
        )
    
    return response
