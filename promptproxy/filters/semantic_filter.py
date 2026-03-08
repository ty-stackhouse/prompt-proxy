"""Semantic redaction filter using Presidio."""

import spacy
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from typing import List, Dict, Any

from ..types import FilterContext, FilterResult, FilterableMessage, MessageFilterResult
from .base import RequestFilter

# Track whether we've warned about missing model to avoid spamming logs
_spacy_warning_issued = False


def check_spacy_model() -> bool:
    """Check if the required spaCy model is available."""
    try:
        spacy.load("en_core_web_sm")
        return True
    except OSError:
        return False


def warn_once_missing_model():
    """Log a warning about missing spaCy model, but only once."""
    global _spacy_warning_issued
    if _spacy_warning_issued:
        return
    _spacy_warning_issued = True
    # The actual warning will be logged by the caller


class SemanticFilter(RequestFilter):
    """PII redaction filter using Microsoft Presidio.
    
    This filter detects and redacts PII entities (person names, emails, etc.)
    from user messages only. System and assistant messages are preserved
    to maintain conversation context.
    
    Entities detected by default:
    - PERSON: People's names
    - EMAIL_ADDRESS: Email addresses
    - LOCATION: Geographic locations
    
    Custom entities can be specified in filter config.
    """
    def __init__(self, config):
        super().__init__(config)
        self.entities = config.entities or ["PERSON", "EMAIL_ADDRESS", "LOCATION"]
        self._nlp = None
        self._analyzer = None
        self._anonymizer = None
        self._checked_model = False
        self._model_available = False

    def _ensure_model(self):
        """Lazily load the spaCy model and engines."""
        if self._checked_model:
            return self._model_available
            
        self._checked_model = True
        if not check_spacy_model():
            warn_once_missing_model()
            self._model_available = False
            return False
            
        self._nlp = spacy.load("en_core_web_sm")
        self._analyzer = AnalyzerEngine()
        self._anonymizer = AnonymizerEngine()
        self._model_available = True
        return True

    async def apply(self, text: str, context: FilterContext) -> FilterResult:
        # Ensure model is loaded
        if not self._ensure_model():
            raise RuntimeError(
                "Semantic filter requires spaCy model 'en_core_web_sm'. "
                "Install it with: make nlp"
            )
        
        # Analyze text
        results = self._analyzer.analyze(text=text, entities=self.entities, language="en")

        if not results:
            return FilterResult(
                text=text,
                changed=False,
                action="pass",
                reason="No entities detected",
                metadata={"entities_found": 0}
            )

        # Anonymize
        anonymized = self._anonymizer.anonymize(text=text, analyzer_results=results)

        return FilterResult(
            text=anonymized.text,
            changed=True,
            action="modify",
            reason=f"Redacted {len(results)} entities",
            metadata={"entities_found": len(results), "entities": [r.entity_type for r in results]}
        )