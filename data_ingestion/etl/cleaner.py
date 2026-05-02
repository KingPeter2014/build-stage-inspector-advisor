"""
data_ingestion/etl/cleaner.py
Text cleaning, normalisation, and PII detection/redaction.
"""
import re
from dataclasses import dataclass

from data_ingestion.sources.base import RawDocument


@dataclass
class CleanedDocument:
    id: str
    content: str
    source: str
    source_type: str
    metadata: dict
    pii_detected: bool = False
    pii_fields_redacted: list[str] = None

    def __post_init__(self):
        if self.pii_fields_redacted is None:
            self.pii_fields_redacted = []


# Basic PII patterns — replace with a dedicated library (presidio, spacy) in production
_PII_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    "phone_us": re.compile(r"\b(\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
}


def clean_text(text: str) -> str:
    """Normalise whitespace, remove control characters, strip boilerplate."""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)  # control chars
    text = re.sub(r"\n{3,}", "\n\n", text)                           # collapse blank lines
    text = re.sub(r"[ \t]{2,}", " ", text)                           # collapse spaces
    return text.strip()


def detect_and_redact_pii(text: str, redact: bool = True) -> tuple[str, list[str]]:
    """Return (processed_text, list_of_detected_pii_types)."""
    detected = []
    for pii_type, pattern in _PII_PATTERNS.items():
        if pattern.search(text):
            detected.append(pii_type)
            if redact:
                text = pattern.sub(f"[{pii_type.upper()}_REDACTED]", text)
    return text, detected


class DocumentCleaner:
    def __init__(self, redact_pii: bool = True, min_length: int = 50):
        self.redact_pii = redact_pii
        self.min_length = min_length

    def process(self, doc: RawDocument) -> CleanedDocument | None:
        content = clean_text(doc.content)
        if len(content) < self.min_length:
            return None   # drop very short / empty documents

        content, pii_fields = detect_and_redact_pii(content, redact=self.redact_pii)

        return CleanedDocument(
            id=doc.id,
            content=content,
            source=doc.source,
            source_type=doc.source_type,
            metadata=doc.metadata,
            pii_detected=bool(pii_fields),
            pii_fields_redacted=pii_fields,
        )
