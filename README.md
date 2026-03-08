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

## Development Environment

PromptProxy uses **uv** with a **project-local `.venv`** for all development tasks. This is the only supported workflow.

### Prerequisites

- Python 3.9+
- `uv` package manager (install with `curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Setup

Clone the repository and run the bootstrap command:

```bash
git clone <this-repo>
cd promptproxy
make bootstrap
```

This creates the project-local `.venv`, installs all Python dependencies (including dev tools), and downloads the spaCy NLP model required for semantic filtering.

### Running Commands

**Use `make` targets or `uv run`:**

```bash
make run        # Start the proxy server
make cli        # Run the CLI chat client
make test       # Run tests
make format     # Format code
make lint       # Lint code
```

**Or use `uv run` directly:**

```bash
uv run python proxy.py    # Start the server
uv run promptproxy        # Run the CLI
uv run pytest             # Run tests
```

### No Manual Activation Needed

Do **not** activate a virtualenv manually. The project uses `uv` to manage the environment automatically:

```bash
# Don't do this:
# source .venv/bin/activate

# Do this instead:
uv run promptproxy
make run
```

If you have an external virtualenv active, PromptProxy will detect it and warn you. Deactivate it and use `uv run` or `make` targets instead.

### Troubleshooting Environment Issues

**Broken `.venv`:**
```bash
rm -rf .venv
make bootstrap
```

**Not running in correct environment:**
```bash
# Check your environment
make env-check

# If you see a warning, deactivate any active virtualenv:
deactivate

# Then use uv run or make targets
uv run promptproxy
```

**NLP model issues:**
```bash
make nlp
```

This will re-sync dependencies and download the spaCy model.

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

1. **Proxy Server**: FastAPI app exposing OpenAI-compatible endpoints
2. **Backend Abstraction**: Pluggable backends (Stub, LiteLLM)
3. **Filter Pipeline**: Configurable transformation filters (request/response stages)
4. **CLI Client**: Terminal-based testing interface

### Message Filtering Architecture

PromptProxy preserves the full OpenAI message structure through the filtering pipeline. This is a key architectural decision that differentiates PromptProxy from simpler proxy implementations.

**How it works:**

1. Incoming messages are converted to `FilterableMessage` objects that wrap the content
2. Filters can operate on individual messages via `apply_messages()` method
3. By default, filters only modify `user` messages - `system` and `assistant` messages are preserved
4. After filtering, messages are converted back to the original format for backend forwarding

**Filter Policy:**

- **User messages**: Fully filterable - content can be transformed, redacted, or rejected
- **System messages**: Preserved unchanged - these provide critical context
- **Assistant messages**: Preserved unchanged - maintains conversation history
- **Tool/function messages**: Preserved unchanged - future compatibility

This design ensures that conversation context is maintained while still allowing policy enforcement on user input.

### Demo Mode

When `ui.demo_mode` is enabled in config.yaml, PromptProxy provides human-friendly output:

- Compact per-request summary to stdout: `✓ [abc123] filters: regex | tokens: 5 → 12 | latency: 150ms`
- Structured JSON logs to stderr (for debugging/audit)
- Clean separation between user-facing output and machine logs

## Terminal Output

PromptProxy has a deliberate three-channel output design:

### Stdout (Human Interface)

Stdout is for intentional, curated product display only:

- **Request display**: When `ui.stdout_display_requests` is enabled, shows input/output request text
- **Format**: Clean human-readable text showing what the request looked like before and after filtering
- **Example**:
  ```
  [abcd1234] PASS
  input request:  Hello, how are you?
  output request: Hello, how are you?
  ```
  Or for modified requests:
  ```
  [abcd1234] MODIFY (regex_filter, denylist_filter)
  input request:  My SSN is 123-45-6789
  output request: My SSN is [REDACTED]
  ```

**Security Note**: Request body display is disabled by default (`ui.stdout_display_requests: false`). Enable it only in development when you want to see request content. Never enable in production where logs might be exposed.

### Stderr (Diagnostics)

Stderr is for warnings and errors only:

- **Format**: Plain text, not JSON: `2026-03-08 16:23:53 WARNING message`
- **Content**: Filter initialization warnings, configuration errors, request rejections
- **Policy**: No INFO-level logs in normal operation - terminal stays clean

### Log File (Machine History)

When `logging.file_path` is configured, detailed structured logs go to the file:

- **Format**: JSON for machine parsing
- **Content**: Full request traces, filter decisions, backend responses, diagnostics
- **Use case**: Debugging, compliance, audit trails

### Startup Output

The server produces minimal startup output:

```
PromptProxy running on http://127.0.0.1:8000
```

No multi-line banners, no Uvicorn access logs, no framework chatter. Warnings during startup still appear on stderr in plain text.

## API Reference

PromptProxy exposes an OpenAI-compatible API surface. Point any OpenAI-compatible client at PromptProxy to use it as a local interception layer.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/v1/models` | List available models |
| `POST` | `/v1/chat/completions` | Chat completion (subset of OpenAI API) |

### POST /v1/chat/completions

Create a chat completion. Accepts an OpenAI-compatible request body.

**Request:**

```json
{
  "model": "gpt-3.5-turbo",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "temperature": 1.0,
  "max_tokens": 1000,
  "top_p": 1.0,
  "n": 1,
  "stream": false,
  "presence_penalty": 0.0,
  "frequency_penalty": 0.0,
  "user": "user-123"
}
```

**Supported fields:**
- `model` (required): Model identifier
- `messages` (required): List of message objects with `role` and `content`
- `temperature`: Sampling temperature (0-2), default 1.0
- `max_tokens`: Maximum tokens to generate, default 1000
- `top_p`: Nucleus sampling, default 1.0
- `n`: Number of completions, default 1
- `stop`: Stop sequences
- `presence_penalty`: Presence penalty, default 0.0
- `frequency_penalty`: Frequency penalty, default 0.0
- `user`: User identifier

**Unsupported fields** (ignored): `stream`, `functions`, `function_call`, `logit_bias`

**Response:**

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1699000000,
  "model": "gpt-3.5-turbo",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 8,
    "total_tokens": 28
  }
}
```

### Error Responses

Errors are returned in OpenAI format:

```json
{
  "error": {
    "message": "Policy rejection: phrase not allowed",
    "type": "invalid_request_error",
    "code": "policy_rejection"
  }
}
```

**Error types:**
- `invalid_request_error`: Malformed request or policy rejection
- `server_error`: Internal server error
- `service_unavailable_error`: Backend unavailable

### Using with OpenAI Clients

```python
from openai import OpenAI

client = OpenAI(
    api_key="dummy-key",  # Not used locally
    base_url="http://127.0.0.1:8000/v1"
)

response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

Or with `curl`:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

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

request_filters:
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

response_filters:
  - name: "noop_filter"
    enabled: false  # placeholder for future response-stage plugins
```

(Existing configs that still use `filters:` will continue working; they are
automatically treated as `request_filters`.)

## Output channels & demo mode

The CLI is designed for live demos, with two distinct streams:

- **stdout**: clean chat transcript and user interaction (what you would show on stage).
- **stderr / file**: detailed operational logs, warnings, trace data. Logging is JSON‑formatted and written to stderr by default; you can also configure a file path. Logs should never pollute the demo output.

A new `ui.demo_mode` setting toggles demo‑friendly behavior (minimal noise on stdout).

### Filter stages

The filter system is now divided into two ordered stages:

- **request_filters** run *before* the backend call.  They can modify or reject
  the prompt text and are stacked in the order defined in configuration.
- **response_filters** run *after* the backend returns.  This stage is currently
  scaffolded with a no‑op default, but will eventually allow transformations
  of model output.

Both sections accept the same plugin names; existing filters are request‑stage
by default.  A migration helper ensures old `filters` entries are treated as
`request_filters`, so existing configs continue to work.


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