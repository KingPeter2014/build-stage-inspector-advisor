"""
data_ingestion/sources/base.py
Abstract base class for all data source connectors.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator


@dataclass
class RawDocument:
    """A raw document pulled from any source before chunking/cleaning."""
    id: str
    content: str
    source: str
    source_type: str                        # "structured" | "unstructured" | "stream" | "api" | "feedback"
    metadata: dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=datetime.utcnow)


class BaseSourceConnector(ABC):
    """All source connectors must implement this interface."""

    @abstractmethod
    def validate_connection(self) -> bool:
        """Verify the source is reachable and credentials are valid."""
        ...

    @abstractmethod
    def fetch(self, **kwargs) -> Iterator[RawDocument]:
        """Yield RawDocument objects from the source."""
        ...

    def fetch_batch(self, batch_size: int = 100, **kwargs) -> Iterator[list[RawDocument]]:
        """Default batched fetch — override for efficiency where needed."""
        batch: list[RawDocument] = []
        for doc in self.fetch(**kwargs):
            batch.append(doc)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch
