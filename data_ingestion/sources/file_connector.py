"""
data_ingestion/sources/file_connector.py
Ingests PDFs, HTML, Markdown, and plain text files from a directory or S3.
"""
import hashlib
from pathlib import Path
from typing import Iterator

import boto3
from bs4 import BeautifulSoup
from pypdf import PdfReader

from data_ingestion.sources.base import BaseSourceConnector, RawDocument


class LocalFileConnector(BaseSourceConnector):
    SUPPORTED = {".pdf", ".html", ".htm", ".md", ".txt"}

    def __init__(self, directory: str):
        self.directory = Path(directory)

    def validate_connection(self) -> bool:
        return self.directory.exists() and self.directory.is_dir()

    def fetch(self, glob: str = "**/*", **kwargs) -> Iterator[RawDocument]:
        for path in self.directory.glob(glob):
            if path.suffix.lower() not in self.SUPPORTED:
                continue
            content = self._extract(path)
            if not content.strip():
                continue
            yield RawDocument(
                id=hashlib.md5(str(path).encode()).hexdigest(),
                content=content,
                source=str(path),
                source_type="unstructured",
                metadata={"filename": path.name, "suffix": path.suffix},
            )

    def _extract(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        if suffix in {".html", ".htm"}:
            soup = BeautifulSoup(path.read_text(errors="ignore"), "html.parser")
            return soup.get_text(separator=" ")
        return path.read_text(errors="ignore")


class S3FileConnector(BaseSourceConnector):
    def __init__(self, bucket: str, prefix: str = "", region: str = "us-east-1"):
        self.bucket = bucket
        self.prefix = prefix
        self._s3 = boto3.client("s3", region_name=region)
        self._local = LocalFileConnector("/tmp/s3_staging")

    def validate_connection(self) -> bool:
        try:
            self._s3.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            return False

    def fetch(self, **kwargs) -> Iterator[RawDocument]:
        import tempfile, os
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                suffix = Path(key).suffix.lower()
                if suffix not in LocalFileConnector.SUPPORTED:
                    continue
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    self._s3.download_file(self.bucket, key, tmp.name)
                    docs = list(LocalFileConnector(os.path.dirname(tmp.name)).fetch())
                    os.unlink(tmp.name)
                for doc in docs:
                    doc.source = f"s3://{self.bucket}/{key}"
                    doc.metadata["s3_key"] = key
                    yield doc
