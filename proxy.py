#!/usr/bin/env python3
"""PromptProxy server entry point."""

import os
import socket
import sys
import uvicorn
from promptproxy.app import app, init_app
from promptproxy.config import load_config

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
    config = load_config()
    init_app(config)
    
    # Pre-bind port check
    host = config.server.host
    port = config.server.port
    if not check_port_available(host, port):
        print(f"ERROR: Cannot bind to {host}:{port} - address already in use.", file=sys.stderr)
        print(f"Either stop the conflicting process or change the port in config.yaml.", file=sys.stderr)
        sys.exit(1)
    
    # Clean startup banner - send to stderr to keep stdout clean for potential pipe usage
    backend_type = config.backend.type
    demo_mode = "enabled" if config.ui.demo_mode else "disabled"
    print(f"PromptProxy starting (PID: {os.getpid()})", file=sys.stderr)
    print(f"  Host: {host}", file=sys.stderr)
    print(f"  Port: {port}", file=sys.stderr)
    print(f"  Backend: {backend_type}", file=sys.stderr)
    print(f"  Demo mode: {demo_mode}", file=sys.stderr)
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="warning",  # Only show warnings and errors from uvicorn
    )

if __name__ == "__main__":
    main()