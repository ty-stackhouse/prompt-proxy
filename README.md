# PromptProxy

A local-first, developer-facing intercepting prompt proxy for LLM traffic. PromptProxy is not "just a PII scrubber" — it's a programmable interception layer for developer AI traffic.

## What is PromptProxy?

PromptProxy sits between your AI client and LLM backends, allowing you to:

- **Observe** all prompts before they reach upstream services
- **Transform** prompts through configurable filters (redaction, substitution, policy enforcement)
- **Forward** modified prompts to any compatible backend
- **Log** everything for debugging and compliance

It's designed for developers who want full control over their AI traffic without sacrificing compatibility with existing OpenAI-style clients.

## Key Features

- **Local-first**: Runs entirely on your machine, no external dependencies required
- **Easy to run**: Single command setup with `uv`
- **Safe by default**: Fail-open behavior, no dangerous code execution
- **Extensible**: Plugin-based filter system for custom transformations
- **Compatible**: OpenAI API compatible, works with existing clients
- **Secure**: Pydantic-validated config, no shell execution, explicit trust boundaries

## Quick Start

### Prerequisites

- Python 3.9+
- `uv` package manager (install with `curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Installation

Clone the repository and run the bootstrap command:

```bash
git clone <this-repo>
cd promptproxy
make bootstrap
```

This installs all Python dependencies (including dev tools) and downloads the spaCy NLP model required for semantic filtering.

### Run the Proxy

Start the server:

```bash
make run
```

The proxy will start on `http://127.0.0.1:8000` by default. It uses the stub backend in demo mode by default.

### Test with CLI

In another terminal, run the CLI client:

```bash
make cli
```

Type messages to interact with the proxy. Use `/quit` to exit.

### Semantic Filtering

PromptProxy includes semantic filtering using spaCy and Presidio for PII detection. The NLP model `en_core_web_sm` is downloaded during `make bootstrap`. If you encounter issues, run `make nlp` manually.

In demo mode (default), the proxy fails open if the model is missing, disabling semantic filtering with a warning.

## Architecture Overview

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Client    │───▶│  PromptProxy │───▶│   Backend   │
│ (OpenAI API)│    │              │    │ (Stub/LiteLLM)
└─────────────┘    └──────────────┘    └─────────────┘
                        │
                        ▼
                   ┌─────────────┐
                   │   Filters   │
                   │ (Pipeline)  │
                   └─────────────┘
```

### Core Components

1. **Proxy Server**: FastAPI app exposing `/v1/chat/completions`
2. **Backend Abstraction**: Pluggable backends (Stub, LiteLLM)
3. **Filter Pipeline**: Configurable transformation filters
4. **CLI Client**: Terminal-based testing interface

## Configuration

Edit `config.yaml`:

```yaml
server:
  host: "127.0.0.1"
  port: 8000
  max_request_size: 1048576  # 1MB
  max_text_length: 100000

backend:
  type: "stub"  # or "litellm"
  litellm:
    model: "gpt-3.5-turbo"
    api_key: "your-key-here"

fail_open: true  # Default: allow requests through on filter errors

logging:
  level: "INFO"
  log_raw_prompt: false  # Don't log original prompts by default
  # Optional file path to persist structured logs in JSON format.
  # Empty string means no file logging; logs still go to stderr.
  file_path: ""

ui:
  demo_mode: false  # when true, CLI only emits chat transcript on stdout

filters:
  - name: "semantic_filter"
    enabled: true
    entities: ["PERSON", "EMAIL_ADDRESS", "LOCATION"]
  - name: "regex_filter"
    enabled: true
    rules:
      - name: "codenames"
        pattern: "\\b(code|secret)\\w+\\b"
        replacement: "[REDACTED_CODENAME]"
  - name: "denylist_filter"
    enabled: true
    rules:
      - phrase: "bad phrase"
        action: "reject"
        message: "This content is not allowed."
  - name: "intercept_filter"
    enabled: false  # Future interactive editing
```

## Output channels & demo mode

The CLI is designed for live demos, with two distinct streams:

- **stdout**: clean chat transcript and user interaction (what you would show on stage).
- **stderr / file**: detailed operational logs, warnings, trace data. Logging is JSON‑formatted and written to stderr by default; you can also configure a file path. Logs should never pollute the demo output.

A new `ui.demo_mode` setting toggles demo‑friendly behavior (minimal noise on stdout).

## Development

Use the Makefile for common tasks:

```bash
make help       # Show available commands
make bootstrap  # Full setup (deps + NLP model)
make run        # Start the proxy server
make cli        # Run the CLI client
make test       # Run tests
make format     # Format code with black
make lint       # Lint code with flake8
```

## Backend Switching

### Stub Backend (Default)

No API keys required, always returns a fixed response.

### LiteLLM Backend

Supports any LLM provider via LiteLLM:

```yaml
backend:
  type: "litellm"
  litellm:
    model: "gpt-3.5-turbo"
    api_key: "sk-..."
```

## Filters

### Semantic Filter

Uses Presidio + spaCy for entity redaction.

**Setup**: `make nlp` to download the required model.

**Config**:
```yaml
- name: "semantic_filter"
  enabled: true
  entities: ["PERSON", "EMAIL_ADDRESS", "LOCATION"]
```

If the model is missing and `fail_open: true`, the filter is automatically disabled with a warning.

### Regex Filter

Pattern-based substitutions from trusted config.

**Config**:
```yaml
- name: "regex_filter"
  enabled: true
  rules:
    - name: "codenames"
      pattern: "\\bsecret\\w+\\b"
      replacement: "[REDACTED]"
```

### Denylist Filter

Policy enforcement with reject/replace actions.

**Config**:
```yaml
- name: "denylist_filter"
  enabled: true
  rules:
    - phrase: "inappropriate content"
      action: "reject"
      message: "Content violates policy."
    - phrase: "mild issue"
      action: "replace"
      replacement: "[FILTERED]"
```

### Intercept Filter

**Future**: Interactive prompt review and editing. Currently a no-op stub.

## Security Notes

### Trust Boundaries

- **Untrusted Input**: All incoming prompt text is treated as untrusted
- **Trusted Config**: Only YAML config is trusted for patterns/rules
- **No Code Execution**: No `eval`, `exec`, or dynamic imports from config
- **No Shell Commands**: Filters cannot execute system commands
- **Validated Config**: All config validated with Pydantic

### Fail-Open Behavior

- `fail_open: true` (default): Allow requests through if filters crash
- `fail_open: false`: Reject requests on filter errors
- Always logged when fail-open allows a request

### Default Security Settings

- Binds to `127.0.0.1` only
- Request size limits: 1MB
- Text length limits: 100k chars
- Raw prompts not logged by default

## Development

### Setup

```bash
uv sync
```

### Run

```bash
make run
```

### Test

```bash
make test
```

### Format

```bash
make format
```

### Lint

```bash
make lint
```

## Future: Intercept-and-Edit-Forward Plugin

A planned interactive filter that:

1. Pauses requests before forwarding
2. Presents transformed prompt to user
3. Allows review and manual editing
4. Continues with user-approved prompt

This will enable workflows like:
- Manual PII review
- Prompt refinement
- Compliance checkpoints

The architecture is designed to add this cleanly as a new filter.

## Contributing

This is an open-source project focused on developer experience and security. Contributions welcome!

## License

MIT License