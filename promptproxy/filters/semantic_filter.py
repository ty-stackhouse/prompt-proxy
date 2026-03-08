"""Semantic redaction filter using Presidio."""

import spacy
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from typing import List

from ..types import FilterContext, FilterResult
from .base import RequestFilter

def check_spacy_model() -> bool:
    """Check if the required spaCy model is available."""
    try:
        spacy.load("en_core_web_sm")
        return True
    except OSError:
        return False

class SemanticFilter(RequestFilter):
    def __init__(self, config):
        super().__init__(config)
        self.entities = config.entities or ["PERSON", "EMAIL_ADDRESS", "LOCATION"]
        self._nlp = None
        self._analyzer = None
        self._anonymizer = None

    def _ensure_model(self):
        """Lazily load the spaCy model and engines."""
        if self._nlp is None:
            if not check_spacy_model():
                raise RuntimeError(
                    "Semantic filter requires spaCy model 'en_core_web_sm'. "
                    "Install it with: make nlp"
                )
            self._nlp = spacy.load("en_core_web_sm")
            self._analyzer = AnalyzerEngine()
            self._anonymizer = AnonymizerEngine()

    async def apply(self, text: str, context: FilterContext) -> FilterResult:
        # Ensure model is loaded
        self._ensure_model()
        
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