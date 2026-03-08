"""Logging configuration."""

import logging
import sys
from typing import Optional
from pythonjsonlogger import jsonlogger

def configure_logging(level: str = "INFO", file_path: Optional[str] = None):
    """Set up the root logger according to the provided options.

    This can be called multiple times; existing handlers on the root logger
    will be cleared before applying the new configuration.  Applications
    should still call it early (e.g. in proxy.main or cli.main) once the
    configuration has been loaded.
    """

    fmt = "%(asctime)s %(name)s %(levelname)s %(message)s"
    formatter = jsonlogger.JsonFormatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    root = logging.getLogger()
    # Remove existing handlers so reconfiguration works in tests / reloads
    for h in list(root.handlers):
        root.removeHandler(h)

    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # stderr handler for console
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(formatter)
    root.addHandler(sh)

    # optional file handler
    if file_path:
        try:
            fh = logging.FileHandler(file_path)
            fh.setFormatter(formatter)
            root.addHandler(fh)
        except Exception:
            # fallback: log a warning to stderr but don't crash
            err = logging.getLogger(__name__)
            err.warning(f"Could not open log file {file_path}, continuing without file handler")


def get_logger(name: str) -> logging.Logger:
    """Return a logger; the root configuration should be applied via
    :func:`configure_logging` first.  Handlers are added only once per
    logger so repeated calls are cheap.
    """
    return logging.getLogger(name)
