"""Custom exceptions and OpenAI-compatible error responses."""

from typing import Optional, Dict, Any
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class PromptProxyError(Exception):
    """Base exception for PromptProxy."""
    pass


class FilterError(PromptProxyError):
    """Error in filter processing."""
    pass


class BackendError(PromptProxyError):
    """Error in backend processing."""
    pass


# -----------------------------------------------------------------------------
# OpenAI-compatible error types
# -----------------------------------------------------------------------------

class OpenAIErrorType:
    """OpenAI error type constants matching their API."""
    INVALID_REQUEST_ERROR = "invalid_request_error"
    AUTHENTICATION_ERROR = "authentication_error"
    PERMISSION_ERROR = "permission_error"
    NOT_FOUND_ERROR = "not_found_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    SERVER_ERROR = "server_error"
    SERVICE_UNAVAILABLE_ERROR = "service_unavailable_error"


class OpenAIErrorCode:
    """Common OpenAI error codes."""
    # General
    NULL = "null"
    # Invalid request errors
    POLICY_REJECTION = "policy_rejection"
    INVALID_API_KEY = "invalid_api_key"
    PARAMETER_INVALID_TYPE = "parameter_invalid_type"
    PARAMETER_MISSING = "parameter_missing"
    PARAMETER_OUT_OF_RANGE = "parameter_out_of_range"
    UNSUPPORTED_PARAMETER = "unsupported_parameter"
    # Server errors
    INTERNAL_ERROR = "internal_error"
    # Rate limit
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


def create_openai_error_response(
    message: str,
    error_type: str = OpenAIErrorType.INVALID_REQUEST_ERROR,
    code: str = OpenAIErrorCode.NULL,
    param: Optional[str] = None,
    status_code: int = 400
) -> JSONResponse:
    """Create an OpenAI-compatible error response.
    
    Args:
        message: Human-readable error message
        error_type: OpenAI error type (e.g., "invalid_request_error")
        code: Specific error code for programmatic handling
        param: Parameter that caused the error (if applicable)
        status_code: HTTP status code
        
    Returns:
        JSONResponse with OpenAI error format
    """
    error_body = {
        "error": {
            "message": message,
            "type": error_type,
            "code": code,
        }
    }
    if param:
        error_body["error"]["param"] = param
    
    return JSONResponse(
        status_code=status_code,
        content=error_body
    )


def policy_rejection_error(message: str, status_code: int = 400) -> JSONResponse:
    """Create an error response for policy rejections (filter blocks)."""
    return create_openai_error_response(
        message=message,
        error_type=OpenAIErrorType.INVALID_REQUEST_ERROR,
        code=OpenAIErrorCode.POLICY_REJECTION,
        status_code=status_code
    )


def invalid_request_error(
    message: str,
    param: Optional[str] = None,
    code: str = OpenAIErrorCode.NULL
) -> JSONResponse:
    """Create an invalid request error response."""
    return create_openai_error_response(
        message=message,
        error_type=OpenAIErrorType.INVALID_REQUEST_ERROR,
        code=code,
        param=param,
        status_code=400
    )


def server_error(message: str = "Internal server error") -> JSONResponse:
    """Create a server error response."""
    return create_openai_error_response(
        message=message,
        error_type=OpenAIErrorType.SERVER_ERROR,
        code=OpenAIErrorCode.INTERNAL_ERROR,
        status_code=500
    )


def service_unavailable_error(message: str = "Service is unavailable") -> JSONResponse:
    """Create a service unavailable error response."""
    return create_openai_error_response(
        message=message,
        error_type=OpenAIErrorType.SERVICE_UNAVAILABLE_ERROR,
        code=OpenAIErrorCode.NULL,
        status_code=503
    )


# -----------------------------------------------------------------------------
# HTTPException wrappers for FastAPI
# -----------------------------------------------------------------------------

class HTTPProxyException(HTTPException):
    """HTTPException with OpenAI-compatible error formatting."""
    
    def __init__(
        self,
        status_code: int,
        message: str,
        error_type: str = OpenAIErrorType.INVALID_REQUEST_ERROR,
        code: str = OpenAIErrorCode.NULL,
        param: Optional[str] = None
    ):
        detail = {
            "message": message,
            "type": error_type,
            "code": code,
        }
        if param:
            detail["param"] = param
        super().__init__(status_code=status_code, detail=detail)