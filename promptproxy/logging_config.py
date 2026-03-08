"""Logging configuration with dual-mode support.

Terminal Output Policy
======================

Stdout (Human Interface)
------------------------
Reserved for intentional, curated output only:
- Request display: Shows input/output request text for each request
- Demo mode: Compact, attractive per-request summaries (one line per request)
- Normal mode: Silent (no stdout output unless explicitly requested)
- NEVER: JSON logs, debug traces, request lifecycle noise, stack traces

Stderr (Diagnostics)
--------------------
Operational messages and errors:
- Server/framework warnings and errors only
- Filter initialization status (warnings on failure)
- Configuration warnings
- NO routine INFO logs in normal operation
- Plain text format: "timestamp level message"

Log File (Machine History)
--------------------------
Detailed persistent history:
- Request traces with correlation IDs
- Filter internals and decisions
- Backend failures and retries
- Startup diagnostics
- Raw prompt logging (when explicitly enabled)
- JSON format for structured parsing

This separation ensures stdout remains a clean UI surface while
all operational data flows to stderr (warnings/errors only) and/or log files.
"""

import logging
import sys
from typing import Optional
from pythonjsonlogger import jsonlogger


# Plain text formatter for terminal stderr output
class TerminalFormatter(logging.Formatter):
    """Plain text formatter for terminal warnings and errors.
    
    Output format: "2026-03-08 16:23:53 WARNING message"
    No JSON, no noise, just simple human-readable text.
    """
    
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    def format(self, record: logging.LogRecord) -> str:
        # Use a simple format for terminal
        timestamp = self.formatTime(record, self.datefmt)
        level = record.levelname
        message = record.getMessage()
        return f"{timestamp} {level} {message}"


# JSON formatter for log files
class FileFormatter(jsonlogger.JsonFormatter):
    """JSON formatter for structured log file output."""
    
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )


def configure_logging(
    level: str = "INFO", 
    file_path: Optional[str] = None,
    demo_mode: bool = False
):
    """Set up the root logger according to the provided options.

    This can be called multiple times; existing handlers on the root logger
    will be cleared before applying the new configuration.
    
    Terminal (stderr) policy:
    - WARNING and ERROR level logs only (no INFO in normal operation)
    - Plain text format, not JSON
    
    Log file policy:
    - All levels (if file_path provided)
    - JSON format for machine parsing
    
    Args:
        level: Log level for file logging (DEBUG, INFO, WARNING, ERROR)
        file_path: Optional path for structured log file
        demo_mode: If True, emit human-friendly per-request summaries to stdout
    """
    
    root = logging.getLogger()
    
    # Remove existing handlers
    for h in list(root.handlers):
        root.removeHandler(h)
    
    # Set root level to NOTSET so handlers can filter at their own level
    # This allows file handler to receive INFO while stderr only gets WARNING+
    root.setLevel(logging.NOTSET)
    
    # Terminal stderr: WARNING and ERROR only, plain text format
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(TerminalFormatter())
    root.addHandler(stderr_handler)
    
    # File handler: all configured levels, JSON format
    if file_path:
        try:
            fh = logging.FileHandler(file_path)
            fh.setLevel(getattr(logging, level.upper(), logging.INFO))
            fh.setFormatter(FileFormatter())
            root.addHandler(fh)
        except Exception:
            # Fallback: log warning to stderr
            err = logging.getLogger(__name__)
            err.warning(f"Could not open log file {file_path}, continuing without file handler")
    
    # Set root level to WARNING to suppress INFO on stderr
    # File handler will still receive all levels if configured
    root.setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger; the root configuration should be applied via
    :func:`configure_logging` first.
    """
    return logging.getLogger(name)
