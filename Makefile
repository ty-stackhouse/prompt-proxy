.PHONY: help bootstrap sync run cli test format lint clean nlp env-check

# =============================================================================
# PromptProxy - uv-managed development environment
# =============================================================================
# This project uses uv with a project-local .venv for all development tasks.
# Do NOT activate an external virtualenv; use `uv run` or `uvx` commands.
# =============================================================================

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

bootstrap: ## Full local setup for PromptProxy (Python deps + NLP model)
	# Sync dependencies first, then download NLP model
	uv sync --group dev --group test
	uv run python -m spacy download en_core_web_sm

sync: ## Sync Python dependencies
	uv sync --group dev --group test

run: ## Run the proxy server
	uv run python proxy.py

cli: ## Run the CLI chat client
	uv run promptproxy

test: ## Run tests
	uv run pytest

format: ## Format code with black
	uv run black .

lint: ## Lint code with flake8
	uv run flake8 .

nlp: ## Download spaCy NLP model for semantic filtering
	# Ensure dependencies are synced first, then download the model
	uv sync --group dev --group test --quiet
	uv pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0.tar.gz

env-check: ## Check if environment is properly configured
	@uv run python -c "from promptproxy.env import check_environment; check_environment()"

clean: ## Clean up cache files
	rm -rf __pycache__ *.pyc *.pyo .pytest_cache .coverage .venv