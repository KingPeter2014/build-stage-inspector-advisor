"""
providers/gcp/data_ingestion/dataflow_connector.py
Cloud Composer (Airflow) DAG trigger + GCS source connector.
Dataflow (Apache Beam) pipeline launcher for large-scale ingestion.

Usage:
    connector = GCSSourceConnector(bucket="my-docs", prefix="raw/")
    docs = connector.fetch()

    launcher = DataflowLauncher()
    job_id = launcher.run_text_pipeline(source_bucket="raw", dest_bucket="processed")
"""
from __future__ import annotations

import hashlib
import json

import requests
from google.auth import default
from google.auth.transport.requests import Request
from google.cloud import storage

from data_ingestion.sources.base import BaseSourceConnector, RawDocument
from providers.gcp.config.settings import get_gcp_settings


class GCSSourceConnector(BaseSourceConnector):
    """
    Reads documents from Google Cloud Storage.
    Supports .txt, .md, .pdf, and .html files.
    """

    def __init__(self, bucket: str | None = None, prefix: str = "") -> None:
        s = get_gcp_settings()
        self._bucket_name = bucket or s.gcs_bucket
        self._prefix = prefix
        self._client = storage.Client(project=s.gcp_project_id)
        self._bucket = self._client.bucket(self._bucket_name)

    def fetch(self) -> list[RawDocument]:
        docs: list[RawDocument] = []
        blobs = self._client.list_blobs(self._bucket_name, prefix=self._prefix)

        for blob in blobs:
            if not any(blob.name.endswith(ext) for ext in (".txt", ".md", ".pdf", ".html")):
                continue
            raw = blob.download_as_bytes()
            content = self._extract(blob.name, raw)
            if not content:
                continue
            docs.append(RawDocument(
                id=hashlib.sha256(blob.name.encode()).hexdigest(),
                source=f"gs://{self._bucket_name}/{blob.name}",
                content=content,
                metadata={"gcs_blob": blob.name, "size": blob.size},
            ))

        return docs

    def _extract(self, name: str, raw: bytes) -> str:
        if name.endswith(".pdf"):
            from pypdf import PdfReader
            import io
            return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(raw)).pages)
        if name.endswith(".html"):
            from bs4 import BeautifulSoup
            return BeautifulSoup(raw, "html.parser").get_text(separator="\n")
        return raw.decode("utf-8", errors="replace")


class DataflowLauncher:
    """
    Launches Apache Beam pipelines on Google Cloud Dataflow.
    Pipelines are defined as separate Beam Python scripts or Flex Templates.
    """

    def __init__(self) -> None:
        s = get_gcp_settings()
        self._settings = s
        self._credentials, self._project = default()

    def run_pipeline(
        self,
        template_path: str,
        job_name: str,
        parameters: dict | None = None,
    ) -> str:
        """Launch a Flex Template Dataflow job; return the job ID."""
        self._credentials.refresh(Request())
        headers = {"Authorization": f"Bearer {self._credentials.token}",
                   "Content-Type": "application/json"}
        s = self._settings
        url = (
            f"https://dataflow.googleapis.com/v1b3/projects/{s.gcp_project_id}"
            f"/locations/{s.gcp_region}/flexTemplates:launch"
        )
        body = {
            "launchParameter": {
                "jobName": job_name,
                "containerSpecGcsPath": template_path,
                "parameters": parameters or {},
                "environment": {"tempLocation": s.dataflow_temp_location},
            }
        }
        resp = requests.post(url, json=body, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()["job"]["id"]
