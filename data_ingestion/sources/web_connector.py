"""
Allowlisted web source connector for official guidance and standards pages.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import json
import logging
from pathlib import Path
from typing import Any, Callable, Iterator
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

from data_ingestion.identity import stable_document_id
from data_ingestion.sources.base import BaseSourceConnector, RawDocument


FetchFn = Callable[[str], tuple[bytes, str]]
log = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebSource:
    url: str
    metadata: dict[str, Any] = field(default_factory=dict)


class WebPageConnector(BaseSourceConnector):
    DEFAULT_ALLOWED_DOMAINS = (
        "consumer.vic.gov.au",
        "www.consumer.vic.gov.au",
        "vba.vic.gov.au",
        "www.vba.vic.gov.au",
        "ncc.abcb.gov.au",
        "www.abcb.gov.au",
        "abcb.gov.au",
        "energy.vic.gov.au",
        "www.energy.vic.gov.au",
    )

    def __init__(
        self,
        sources: list[WebSource],
        *,
        allowed_domains: tuple[str, ...] | None = None,
        timeout_seconds: float = 30.0,
        fetcher: FetchFn | None = None,
        skip_errors: bool = True,
    ) -> None:
        self.sources = sources
        self.allowed_domains = allowed_domains or self.DEFAULT_ALLOWED_DOMAINS
        self.timeout_seconds = timeout_seconds
        self.fetcher = fetcher
        self.skip_errors = skip_errors

    @classmethod
    def from_manifest(cls, manifest_path: str | Path) -> "WebPageConnector":
        data = json.loads(Path(manifest_path).read_text())
        sources = [
            WebSource(url=item["url"], metadata=dict(item.get("metadata") or {}))
            for item in data
        ]
        return cls(sources)

    def validate_connection(self) -> bool:
        return all(self._is_allowed(source.url) for source in self.sources)

    def fetch(self, **kwargs) -> Iterator[RawDocument]:
        for source in self.sources:
            if not self._is_allowed(source.url):
                raise ValueError(f"Web source is not allowlisted: {source.url}")
            try:
                body, content_type = self._fetch(source.url)
            except Exception as exc:
                if not self.skip_errors:
                    raise
                log.warning("Skipping web source %s: %s", source.url, exc)
                continue
            text = self._extract_text(source.url, body, content_type)
            if not text.strip():
                continue
            metadata = {
                "source_uri": source.url,
                "source_type": "web",
                **source.metadata,
            }
            yield RawDocument(
                id=stable_document_id(source.url),
                content=text,
                source=source.url,
                source_type="web",
                metadata=metadata,
            )

    def _is_allowed(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return host in self.allowed_domains

    def _fetch(self, url: str) -> tuple[bytes, str]:
        if self.fetcher:
            return self.fetcher(url)
        headers = {"User-Agent": "build-stage-inspector-advisor/0.1"}
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content, response.headers.get("content-type", "")

    def _extract_text(self, url: str, body: bytes, content_type: str) -> str:
        if "pdf" in content_type.lower() or url.lower().endswith(".pdf"):
            reader = PdfReader(BytesIO(body))
            return "\n".join(page.extract_text() or "" for page in reader.pages)

        soup = BeautifulSoup(body, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        main = soup.find("main") or soup.body or soup
        text = main.get_text(separator=" ", strip=True)
        return f"{title}\n\n{text}".strip()
