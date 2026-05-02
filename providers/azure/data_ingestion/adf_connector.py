"""
providers/azure/data_ingestion/adf_connector.py
Azure Data Factory pipeline trigger + ADLS Gen2 source connector.

Usage:
    connector = ADFConnector()
    connector.trigger_pipeline("IngestRawDocs", parameters={"source": "blob"})

    adls = ADLSGen2Connector(container="raw-docs")
    docs = adls.fetch()
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.mgmt.datafactory import DataFactoryManagementClient
from azure.storage.blob import BlobServiceClient

from data_ingestion.sources.base import BaseSourceConnector, RawDocument
from providers.azure.config.settings import get_azure_settings


class ADFConnector:
    """Triggers Azure Data Factory pipelines and polls run status."""

    def __init__(self) -> None:
        s = get_azure_settings()
        credential = DefaultAzureCredential()
        self._client = DataFactoryManagementClient(credential, s.azure_subscription_id)
        self._rg = s.azure_data_factory_resource_group
        self._factory = s.azure_data_factory_name

    def trigger_pipeline(
        self,
        pipeline_name: str,
        parameters: dict[str, Any] | None = None,
    ) -> str:
        """Trigger a pipeline run; return the run ID."""
        from azure.mgmt.datafactory.models import CreateRunResponse
        response: CreateRunResponse = self._client.pipelines.create_run(
            resource_group_name=self._rg,
            factory_name=self._factory,
            pipeline_name=pipeline_name,
            parameters=parameters or {},
        )
        return response.run_id

    def get_run_status(self, run_id: str) -> str:
        """Return the status of a pipeline run: Queued | InProgress | Succeeded | Failed."""
        run = self._client.pipeline_runs.get(
            resource_group_name=self._rg,
            factory_name=self._factory,
            run_id=run_id,
        )
        return run.status


class ADLSGen2Connector(BaseSourceConnector):
    """
    Reads documents from Azure Data Lake Storage Gen2 (Blob Storage API).
    Supports .txt, .md, .pdf, and .html files.
    """

    def __init__(
        self,
        container: str | None = None,
        prefix: str = "",
    ) -> None:
        s = get_azure_settings()
        self._container = container or s.azure_storage_container
        self._prefix = prefix
        self._service = BlobServiceClient(
            account_url=f"https://{s.azure_storage_account_name}.blob.core.windows.net",
            credential=DefaultAzureCredential(),
        )

    def fetch(self) -> list[RawDocument]:
        container_client = self._service.get_container_client(self._container)
        docs: list[RawDocument] = []

        for blob in container_client.list_blobs(name_starts_with=self._prefix):
            name: str = blob.name
            if not any(name.endswith(ext) for ext in (".txt", ".md", ".pdf", ".html")):
                continue

            blob_client = container_client.get_blob_client(name)
            raw_bytes = blob_client.download_blob().readall()
            content = self._extract(name, raw_bytes)
            if not content:
                continue

            docs.append(RawDocument(
                id=hashlib.sha256(name.encode()).hexdigest(),
                source=f"adls://{self._container}/{name}",
                content=content,
                metadata={"blob_name": name, "size": blob.size},
            ))

        return docs

    def _extract(self, name: str, raw: bytes) -> str:
        if name.endswith(".pdf"):
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        if name.endswith(".html"):
            from bs4 import BeautifulSoup
            return BeautifulSoup(raw, "html.parser").get_text(separator="\n")
        return raw.decode("utf-8", errors="replace")
