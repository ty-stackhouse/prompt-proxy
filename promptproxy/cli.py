#!/usr/bin/env python3
"""PromptProxy CLI chat client."""

import asyncio
import sys
from typing import Optional

import httpx
import logging
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.text import Text

from promptproxy.config import load_config
from promptproxy.logging_config import configure_logging
from promptproxy.env import check_environment

# chat console writes to stdout
chat_console = Console()
# helper for any CLI-specific warnings/errors; writes to stderr
log_console = Console(stderr=True)

logger = logging.getLogger(__name__)

def main():
    # Check environment before proceeding
    check_environment()
    
    config = load_config()
    # configure logging according to config; output goes to stderr/file
    configure_logging(level=config.logging.level, file_path=config.logging.file_path)
    base_url = f"http://{config.server.host}:{config.server.port}"

    chat_console.print("[bold green]PromptProxy CLI Chat Client[/bold green]")
    chat_console.print(f"Connected to: {base_url}")
    chat_console.print("Type your message, paste from clipboard, or '/quit' to exit.\n")

    if config.ui.demo_mode:
        chat_console.print("[bold magenta]DEMO MODE ENABLED[/bold magenta]\n")

    while True:
        try:
            user_input = Prompt.ask("[bold blue]You[/bold blue]").strip()
            if user_input.lower() in ["/quit", "quit"]:
                chat_console.print("[yellow]Goodbye![/yellow]")
                break

            if not user_input:
                continue

            # Send to proxy
            response = send_request(base_url, user_input)
            if response:
                display_response(response)
            else:
                # show failure on stderr but don't contaminate chat transcript
                log_console.print("[red]Failed to get response from proxy.[/red]")

        except KeyboardInterrupt:
            log_console.print("\n[yellow]Interrupted. Goodbye![/yellow]")
            break
        except Exception as e:
            log_console.print(f"[red]Error: {e}[/red]")

def send_request(base_url: str, message: str) -> Optional[dict]:
    """Send chat request to proxy."""
    payload = {
        "model": "gpt-3.5-turbo",  # Default model
        "messages": [{"role": "user", "content": message}],
        "max_tokens": 1000,
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{base_url}/v1/chat/completions", json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as e:
        log_console.print(f"[red]Request error: {e}[/red]")
        logger.error("request error", exc_info=e)
        return None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            # Likely policy rejection
            try:
                error_data = e.response.json()
                log_console.print(f"[red]Policy rejection: {error_data.get('error', {}).get('message', 'Unknown error')}[/red]")
            except:
                log_console.print(f"[red]HTTP {e.response.status_code}: {e.response.text}[/red]")
        else:
            log_console.print(f"[red]HTTP {e.response.status_code}: {e.response.text}[/red]")
        logger.error("http status error", exc_info=e)
        return None

def display_response(response: dict):
    """Display the assistant response."""
    if "choices" in response and response["choices"]:
        content = response["choices"][0]["message"]["content"]
        panel = Panel.fit(
            Text(content, style="green"),
            title="[bold green]Assistant[/bold green]",
            border_style="green"
        )
        chat_console.print(panel)
    else:
        log_console.print("[red]Invalid response format.[/red]")

if __name__ == "__main__":
    main()