"""FastAPI application for PromptProxy.

OpenAI-compatible local interception proxy.

Supported endpoints:
- POST /v1/chat/completions: Chat completion API (subset)
- GET /v1/models: List available models
- GET /health: Health check
"""

import uuid
from typing import List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import Config
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
from .pipeline import Pipeline
from .backends import get_backend
from .logging_config import configure_logging
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
    version="0.1.0",
    description="OpenAI-compatible local interception proxy for LLM traffic"
)

config: Config = None
pipeline: Pipeline = None
backend = None


def init_app(cfg: Config):
    global config, pipeline, backend
    config = cfg
    # configure logging before anything else so that early messages obey settings
    configure_logging(level=config.logging.level, file_path=config.logging.file_path)
    register_filters()
    pipeline = Pipeline(config)
    backend = get_backend(config)


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

@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest, req: Request):
    """Handle chat completion requests.
    
    OpenAI-compatible endpoint. Accepts a subset of the OpenAI Chat API
    and returns responses in OpenAI format.
    
    Request filtering:
    - Runs request filters on the user prompt
    - Rejects with policy_rejection error if filter rejects
    
    Response handling:
    - Forwards to backend
    - Optionally runs response filters
    - Returns OpenAI-style response
    """
    correlation_id = str(uuid.uuid4())
    logger.info(f"[{correlation_id}] Request started", extra={"correlation_id": correlation_id})

    # Validate: require at least one user message
    user_messages = [msg for msg in request.messages if msg.role == "user"]
    if not user_messages:
        logger.warning(f"[{correlation_id}] No user messages found", extra={"correlation_id": correlation_id})
        return invalid_request_error(
            message="No user messages found",
            param="messages",
            code="empty_messages"
        )

    # Combine user message content
    prompt_text = " ".join(msg.content for msg in user_messages)
    logger.info(f"[{correlation_id}] Original prompt length: {len(prompt_text)} chars", extra={"correlation_id": correlation_id})

    # Run request-stage filters
    try:
        result = await pipeline.process_request(prompt_text, correlation_id)
        if result.action == "reject":
            logger.warning(f"[{correlation_id}] Request rejected: {result.reason}", extra={"correlation_id": correlation_id})
            return policy_rejection_error(message=f"Policy rejection: {result.reason}")

        transformed_text = result.text
        logger.info(f"[{correlation_id}] Transformed prompt length: {len(transformed_text)} chars", extra={"correlation_id": correlation_id})
        
        if config.logging.log_raw_prompt:
            logger.info(f"[{correlation_id}] Raw prompt: {prompt_text}", extra={"correlation_id": correlation_id})
        logger.info(f"[{correlation_id}] Transformed prompt: {transformed_text}", extra={"correlation_id": correlation_id})

    except Exception as e:
        if config.fail_open:
            logger.warning(f"[{correlation_id}] Request pipeline error, failing open: {e}", extra={"correlation_id": correlation_id})
            transformed_text = prompt_text
        else:
            logger.error(f"[{correlation_id}] Request pipeline error, rejecting: {e}", extra={"correlation_id": correlation_id})
            return server_error(message="Internal processing error")

    # Forward to backend
    try:
        backend_response = await backend.generate(
            messages=[Message(role="user", content=transformed_text)],
            model=request.model,
            options={
                "max_tokens": request.max_tokens, 
                "temperature": request.temperature,
                "top_p": request.top_p,
                "n": request.n,
                "stop": request.stop,
            }
        )
        logger.info(f"[{correlation_id}] Backend response received", extra={"correlation_id": correlation_id})
    except Exception as e:
        logger.error(f"[{correlation_id}] Backend error: {e}", extra={"correlation_id": correlation_id})
        return service_unavailable_error(message=f"Backend error: {str(e)}")

    # Optionally run response-stage filters on the text returned by the backend
    raw_content = backend_response.get("content", "")
    resp_result = await pipeline.process_response(raw_content, correlation_id)
    if resp_result.changed:
        logger.info(f"[{correlation_id}] Response text modified by filters", extra={"correlation_id": correlation_id})
    if resp_result.action == "reject":
        # We don't fail the HTTP request, but we log the rejection for observability
        logger.warning(f"[{correlation_id}] Response rejected by filter: {resp_result.reason}", extra={"correlation_id": correlation_id})
    final_content = resp_result.text

    # Calculate token counts (approximate)
    prompt_tokens = len(transformed_text.split())
    completion_tokens = len(final_content.split())
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

    logger.info(f"[{correlation_id}] Request completed", extra={"correlation_id": correlation_id})
    return response