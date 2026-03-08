"""Custom exceptions."""

class PromptProxyError(Exception):
    """Base exception for PromptProxy."""
    pass

class FilterError(PromptProxyError):
    """Error in filter processing."""
    pass

class BackendError(PromptProxyError):
    """Error in backend processing."""
    pass