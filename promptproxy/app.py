"""FastAPI application for PromptProxy."""

import uuid
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from .config import Config
from .models import ChatCompletionRequest, ChatCompletionResponse, Message
from .pipeline import Pipeline
from .backends import get_backend
from .logging_config import configure_logging
import logging
from .filters import register_filters

# logger instance (handlers attached when logging is configured)
logger = logging.getLogger(__name__)

app = FastAPI(title="PromptProxy", version="0.1.0")

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
    return {"status": "healthy"}

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, req: Request):
    correlation_id = str(uuid.uuid4())
    logger.info(f"[{correlation_id}] Request started", extra={"correlation_id": correlation_id})

    # Extract prompt text
    user_messages = [msg for msg in request.messages if msg.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user messages found")

    prompt_text = " ".join(msg.content for msg in user_messages)
    logger.info(f"[{correlation_id}] Original prompt length: {len(prompt_text)}", extra={"correlation_id": correlation_id})

    # Run through pipeline
    try:
        result = await pipeline.process(prompt_text, correlation_id)
        if result.action == "reject":
            logger.warning(f"[{correlation_id}] Request rejected: {result.reason}", extra={"correlation_id": correlation_id})
            raise HTTPException(status_code=400, detail=result.reason)

        transformed_text = result.text
        logger.info(f"[{correlation_id}] Transformed prompt length: {len(transformed_text)}", extra={"correlation_id": correlation_id})
        if config.logging.log_raw_prompt:
            logger.info(f"[{correlation_id}] Raw prompt: {prompt_text}", extra={"correlation_id": correlation_id})
        logger.info(f"[{correlation_id}] Transformed prompt: {transformed_text}", extra={"correlation_id": correlation_id})

    except Exception as e:
        if config.fail_open:
            logger.warning(f"[{correlation_id}] Pipeline error, failing open: {e}", extra={"correlation_id": correlation_id})
            transformed_text = prompt_text
        else:
            logger.error(f"[{correlation_id}] Pipeline error, rejecting: {e}", extra={"correlation_id": correlation_id})
            raise HTTPException(status_code=500, detail="Internal processing error")

    # Forward to backend
    try:
        backend_response = await backend.generate(
            messages=[Message(role="user", content=transformed_text)],
            model=request.model,
            options={"max_tokens": request.max_tokens, "temperature": request.temperature}
        )
        logger.info(f"[{correlation_id}] Backend response received", extra={"correlation_id": correlation_id})
    except Exception as e:
        logger.error(f"[{correlation_id}] Backend error: {e}", extra={"correlation_id": correlation_id})
        raise HTTPException(status_code=502, detail="Backend error")

    # Return OpenAI-style response
    response = ChatCompletionResponse(
        id=f"chatcmpl-{correlation_id}",
        object="chat.completion",
        created=int(uuid.uuid1().time // 1000000),
        model=request.model,
        choices=[
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": backend_response.get("content", ""),
                },
                "finish_reason": "stop",
            }
        ],
        usage={
            "prompt_tokens": len(transformed_text.split()),
            "completion_tokens": len(backend_response.get("content", "").split()),
            "total_tokens": len(transformed_text.split()) + len(backend_response.get("content", "").split()),
        }
    )

    logger.info(f"[{correlation_id}] Request completed", extra={"correlation_id": correlation_id})
    return response