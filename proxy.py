#!/usr/bin/env python3
"""PromptProxy server entry point."""

import sys
import uvicorn
from promptproxy.app import app, init_app
from promptproxy.config import load_config

def check_prerequisites(config):
    """Check for required runtime assets and warn/fail as appropriate."""
    from promptproxy.filters.semantic_filter import check_spacy_model
    
    semantic_enabled = any(f.name == "semantic_filter" and f.enabled for f in config.filters)
    if semantic_enabled and not check_spacy_model():
        if config.fail_open:
            print("WARNING: Semantic filter is enabled but spaCy model 'en_core_web_sm' is missing.", file=sys.stderr)
            print("The filter will be disabled. To enable semantic filtering, run: make nlp", file=sys.stderr)
        else:
            print("ERROR: Semantic filter is enabled but spaCy model 'en_core_web_sm' is missing.", file=sys.stderr)
            print("Install it with: make nlp", file=sys.stderr)
            print("Or set fail_open: true in config.yaml to disable the filter gracefully.", file=sys.stderr)
            sys.exit(1)

def main():
    config = load_config()
    check_prerequisites(config)
    init_app(config)
    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level=config.logging.level.lower(),
    )

if __name__ == "__main__":
    main()