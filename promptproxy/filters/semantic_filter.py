"""Semantic redaction filter using Presidio."""

import spacy
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from typing import List

from ..types import FilterContext, FilterResult
from .base import BaseFilter

def check_spacy_model() -> bool:
    """Check if the required spaCy model is available."""
    try:
        spacy.load("en_core_web_sm")
        return True
    except OSError:
        return False

class SemanticFilter(BaseFilter):
    def __init__(self, config):
        super().__init__(config)
        self.entities = config.entities or ["PERSON", "EMAIL_ADDRESS", "LOCATION"]
        if not check_spacy_model():
            raise RuntimeError(
                "Semantic filter requires spaCy model 'en_core_web_sm'. "
                "Install it with: uv run python -m spacy download en_core_web_sm"
            )
        self.nlp = spacy.load("en_core_web_sm")
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()

    async def apply(self, text: str, context: FilterContext) -> FilterResult:
        # Analyze text
        results = self.analyzer.analyze(text=text, entities=self.entities, language="en")

        if not results:
            return FilterResult(
                text=text,
                changed=False,
                action="pass",
                reason="No entities detected",
                metadata={"entities_found": 0}
            )

        # Anonymize
        anonymized = self.anonymizer.anonymize(text=text, analyzer_results=results)

        return FilterResult(
            text=anonymized.text,
            changed=True,
            action="modify",
            reason=f"Redacted {len(results)} entities",
            metadata={"entities_found": len(results), "entities": [r.entity_type for r in results]}
        )