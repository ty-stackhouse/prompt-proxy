#!/usr/bin/env python3
"""PromptProxy CLI chat client."""

import asyncio
import sys
from typing import Optional

import httpx
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.text import Text

from promptproxy.config import load_config

console = Console()

def main():
    config = load_config()
    base_url = f"http://{config.server.host}:{config.server.port}"

    console.print("[bold green]PromptProxy CLI Chat Client[/bold green]")
    console.print(f"Connected to: {base_url}")
    console.print("Type your message, paste from clipboard, or '/quit' to exit.\n")

    while True:
        try:
            user_input = Prompt.ask("[bold blue]You[/bold blue]").strip()
            if user_input.lower() in ["/quit", "quit"]:
                console.print("[yellow]Goodbye![/yellow]")
                break

            if not user_input:
                continue

            # Send to proxy
            response = send_request(base_url, user_input)
            if response:
                display_response(response)
            else:
                console.print("[red]Failed to get response from proxy.[/red]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Goodbye![/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

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
        console.print(f"[red]Request error: {e}[/red]")
        return None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            # Likely policy rejection
            try:
                error_data = e.response.json()
                console.print(f"[red]Policy rejection: {error_data.get('error', {}).get('message', 'Unknown error')}[/red]")
            except:
                console.print(f"[red]HTTP {e.response.status_code}: {e.response.text}[/red]")
        else:
            console.print(f"[red]HTTP {e.response.status_code}: {e.response.text}[/red]")
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
        console.print(panel)
    else:
        console.print("[red]Invalid response format.[/red]")

if __name__ == "__main__":
    main()