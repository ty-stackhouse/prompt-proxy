# Environment Recovery Guide

This document provides instructions for maintainers and contributors to recover from common environment issues.

## Quick Recovery

### Broken or Corrupted `.venv`

If the project-local `.venv` is broken, stale, or causing unexpected behavior:

```bash
# Remove the corrupted environment
rm -rf .venv

# Re-create from scratch
make bootstrap

# Or step by step:
uv sync --group dev --group test
make nlp
```

### NLP Model Issues

If spaCy model downloads fail or the semantic filter doesn't work:

```bash
# Re-download the model
make nlp

# Or manually:
uv pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0.tar.gz
```

### External Virtualenv Interference

If you have an external virtualenv active and commands behave unexpectedly:

```bash
# Deactivate any active virtualenv
deactivate

# Use uv run or make targets instead
uv run promptproxy
make run
make cli
make test
```

### Complete Reset

For a completely fresh start:

```bash
# Remove all generated files
make clean

# Remove the virtual environment
rm -rf .venv

# Re-setup everything
make bootstrap
```

## Environment Check

Use the environment check target to diagnose issues:

```bash
make env-check
```

This will:
- Verify `.venv` exists
- Detect if an external virtualenv is active
- Provide actionable guidance

## Troubleshooting Common Issues

### "No module named pip" Error

This occurs when the venv is incomplete or corrupted:

```bash
rm -rf .venv
uv sync --group dev --group test
```

### Commands fail after `uv sync`

Try re-running sync:

```bash
uv sync --group dev --group test
```

### spaCy model not found

Reinstall the model:

```bash
make nlp
```

### Tests hanging or timing out

Some tests (like API tests) may start servers or make network calls. Run tests with a timeout:

```bash
uv run pytest --ignore=tests/test_pipeline.py -q
```

## Best Practices

1. **Always use `uv run` or `make` targets** - Never activate `.venv` manually
2. **Run `make bootstrap` after cloning** - This sets up everything correctly
3. **Use `make env-check` if things behave unexpectedly**
4. **Delete `.venv` if you suspect corruption** - It's fast to recreate

## Understanding the Workflow

PromptProxy uses **uv** with a **project-local `.venv`**:

- `uv sync` creates `.venv` and installs dependencies
- `uv run` executes commands in the managed environment
- `make` targets wrap `uv run` for convenience
- No manual virtualenv activation needed

This ensures consistent, reproducible environments across all platforms.