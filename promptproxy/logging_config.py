"""Logging configuration with dual-mode support.

Terminal Output Policy
======================

Stdout (Human Interface)
------------------------
Reserved for intentional, curated output only:
- Demo mode: Compact, attractive per-request summaries (one line per request)
- Normal mode: Silent (no stdout output unless explicitly requested)
- NEVER: JSON logs, debug traces, request lifecycle noise, stack traces

Stderr (Diagnostics)
--------------------
Operational messages and errors:
- Server/framework diagnostics
- Filter initialization status (warnings on failure)
- Request errors and rejections
- Configuration warnings
- Any structured logs for terminal debugging

Log File (Machine History)
--------------------------
Detailed persistent history:
- Request traces with correlation IDs
- Filter internals and decisions
- Backend failures and retries
- Startup diagnostics
- Raw prompt logging (when explicitly enabled)

This separation ensures stdout remains a clean UI surface while
all operational data flows to stderr and/or log files.
"""

import logging
import sys
from typing import Optional
from pythonjsonlogger import jsonlogger
from dataclasses import dataclass


@dataclass
class DemoOutput:
    """Human-friendly demo output to stdout."""
    correlation_id: str
    action: str  # pass, modify, reject
    filters: list
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    
    def format(self) -> str:
        """Format as a compact, attractive summary line."""
        filter_str = ", ".join(self.filters) if self.filters else "none"
        action_emoji = {
            "pass": "✓",
            "modify": "↔", 
            "reject": "✗"
        }.get(self.action, "?")
        
        return (
            f"{action_emoji} [{self.correlation_id[:8]}] "
            f"filters: {filter_str} | "
            f"tokens: {self.prompt_tokens} → {self.completion_tokens} | "
            f"latency: {self.latency_ms:.0f}ms"
        )


class DemoFormatter(logging.Formatter):
    """Human-friendly formatter for demo mode stdout output.
    
    This formatter produces compact, colored, summary-style output
    that's useful for demos but not for debugging.
    """
    
    # ANSI color codes
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    def __init__(self, use_color: bool = True):
        super().__init__()
        self.use_color = use_color
    
    def format(self, record: logging.LogRecord) -> str:
        # Only format demo-related INFO messages
        if hasattr(record, 'demo_output'):
            return record.demo_output
        
        # For other messages, use simple format
        msg = f"{record.levelname}: {record.getMessage()}"
        if self.use_color:
            if record.levelno >= logging.ERROR:
                return f"{self.RED}{msg}{self.RESET}"
            elif record.levelno >= logging.WARNING:
                return f"{self.YELLOW}{msg}{self.RESET}"
        return msg


class StructuredLogger:
    """Dual-output logger that writes structured JSON to stderr/file
    and human-readable demo output to stdout when enabled.
    """
    
    def __init__(
        self, 
        level: str = "INFO", 
        file_path: Optional[str] = None,
        demo_mode: bool = False
    ):
        self.level = getattr(logging, level.upper(), logging.INFO)
        self.demo_mode = demo_mode
        self._configure_root_logger(file_path)
    
    def _configure_root_logger(self, file_path: Optional[str]):
        """Configure the root logger with JSON formatting for stderr/file."""
        fmt = "%(asctime)s %(name)s %(levelname)s %(message)s"
        formatter = jsonlogger.JsonFormatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
        
        root = logging.getLogger()
        # Remove existing handlers
        for h in list(root.handlers):
            root.removeHandler(h)
        
        root.setLevel(self.level)
        
        # stderr handler for structured logs
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(formatter)
        root.addHandler(sh)
        
        # Optional file handler
        if file_path:
            try:
                fh = logging.FileHandler(file_path)
                fh.setFormatter(formatter)
                root.addHandler(fh)
            except Exception:
                # Fallback: log warning to stderr
                err = logging.getLogger(__name__)
                err.warning(f"Could not open log file {file_path}, continuing without file handler")
    
    def get_logger(self, name: str) -> logging.Logger:
        """Return a configured logger."""
        return logging.getLogger(name)
    
    @staticmethod
    def emit_demo_output(
        correlation_id: str,
        action: str,
        filters: list,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float
    ):
        """Emit a demo-friendly output line to stdout.
        
        This bypasses the normal logging system to write directly to stdout
        for clean demo output that doesn't interleave with structured logs.
        """
        output = DemoOutput(
            correlation_id=correlation_id,
            action=action,
            filters=filters,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms
        )
        print(output.format())


def configure_logging(
    level: str = "INFO", 
    file_path: Optional[str] = None,
    demo_mode: bool = False
):
    """Set up the root logger according to the provided options.

    This can be called multiple times; existing handlers on the root logger
    will be cleared before applying the new configuration.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        file_path: Optional path for structured log file
        demo_mode: If True, emit human-friendly per-request summaries to stdout
    """
    
    # In demo mode, we configure a simpler logging setup
    if demo_mode:
        _configure_demo_mode(level, file_path)
    else:
        _configure_production_mode(level, file_path)


def _configure_demo_mode(level: str, file_path: Optional[str]):
    """Configure logging for demo mode - quiet stderr, formatted stdout."""
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    
    # Set root to WARNING to minimize noise on stderr
    root.setLevel(logging.WARNING)
    
    # stderr: warnings and errors only (minimal noise)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(
        logging.Formatter("%(levelname)s: %(message)s")
    )
    root.addHandler(stderr_handler)
    
    # stdout: demo output only - clean curated interface
    # Set the demo logger to DEBUG so demo output prints to stdout
    demo_logger = logging.getLogger("promptproxy.demo")
    demo_logger.setLevel(logging.DEBUG)
    demo_logger.propagate = False  # Don't send to root
    
    # Direct stdout handler for demo output (no filter needed - dedicated logger)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    # Use a simple formatter that just outputs the message
    stdout_handler.setFormatter(logging.Formatter("%(message)s"))
    demo_logger.addHandler(stdout_handler)
    
    # Optional file handler for full logs
    if file_path:
        try:
            fh = logging.FileHandler(file_path)
            fh.setFormatter(jsonlogger.JsonFormatter(
                "%(asctime)s %(name)s %(levelname)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            ))
            root.addHandler(fh)
        except Exception:
            pass  # Silently skip file logging if it fails


def _configure_production_mode(level: str, file_path: Optional[str]):
    """Configure logging for production - structured JSON everywhere."""
    fmt = "%(asctime)s %(name)s %(levelname)s %(message)s"
    formatter = jsonlogger.JsonFormatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
    
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # stderr handler
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(formatter)
    root.addHandler(sh)
    
    # Optional file handler
    if file_path:
        try:
            fh = logging.FileHandler(file_path)
            fh.setFormatter(formatter)
            root.addHandler(fh)
        except Exception:
            err = logging.getLogger(__name__)
            err.warning(f"Could not open log file {file_path}, continuing without file handler")


class _DemoFilter(logging.Filter):
    """Filter that only allows demo-specific log records to stdout."""
    def filter(self, record: logging.LogRecord) -> bool:
        # Allow records with demo_output attribute
        return hasattr(record, 'demo_output')


def get_logger(name: str) -> logging.Logger:
    """Return a logger; the root configuration should be applied via
    :func:`configure_logging` first.
    """
    return logging.getLogger(name)


def log_demo_summary(
    correlation_id: str,
    action: str,
    filters: list,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float
):
    """Log a demo-friendly summary to stdout.
    
    In demo mode, this prints a compact human-readable line to stdout.
    Uses a dedicated logger to ensure clean separation from other logs.
    """
    logger = logging.getLogger("promptproxy.demo")
    
    # Create the formatted output
    output = DemoOutput(
        correlation_id=correlation_id,
        action=action,
        filters=filters,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms
    )
    
    # Emit directly to stdout in demo mode (clean interface)
    if logger.level <= logging.INFO:
        print(output.format())
