.PHONY: help bootstrap sync run cli test format lint clean nlp

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

bootstrap: ## Full local setup for PromptProxy (Python deps + NLP model)
	uv sync --group dev --group test
	$(MAKE) nlp

sync: ## Sync Python dependencies (alias for bootstrap)
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
	uv run python -m spacy download en_core_web_sm

clean: ## Clean up cache files
	rm -rf __pycache__ *.pyc *.pyo .pytest_cache .coverage