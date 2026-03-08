#!/usr/bin/env python3
"""PromptProxy server entry point."""

import os
import socket
import sys
import logging
import uvicorn
from promptproxy.app import app, init_app
from promptproxy.config import load_config
from promptproxy.env import check_environment

# Configure uvicorn logger to be quiet (only warnings/errors)
uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.setLevel(logging.WARNING)


def check_port_available(host: str, port: int) -> bool:
    """Check if a TCP port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def main():
    # Check environment before proceeding
    check_environment()
    
    config = load_config()
    init_app(config)
    
    # Pre-bind port check
    host = config.server.host
    port = config.server.port
    if not check_port_available(host, port):
        print(f"ERROR: Cannot bind to {host}:{port} - address already in use.", file=sys.stderr)
        print(f"Either stop the conflicting process or change the port in config.yaml.", file=sys.stderr)
        sys.exit(1)
    
    # Minimal startup banner - single line to stderr
    print(f"PromptProxy running on http://{host}:{port}", file=sys.stderr)
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="warning",  # Only show warnings and errors from uvicorn
        access_log=False,      # Disable access log spam
    )


if __name__ == "__main__":
    main()