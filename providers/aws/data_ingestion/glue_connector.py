"""
providers/aws/data_ingestion/glue_connector.py
AWS Glue ETL — catalog crawler trigger + S3 source connector.

Usage:
    connector = GlueConnector()
    connector.start_crawler("llmops-crawler")

    s3 = S3SourceConnector(bucket="my-docs", prefix="raw/")
    docs = s3.fetch()
"""
from __future__ import annotations

import hashlib
import time

import boto3

from data_ingestion.sources.base import BaseSourceConnector, RawDocument
from providers.aws.config.settings import get_aws_settings


class GlueConnector:
    """Triggers AWS Glue crawlers and ETL jobs via boto3."""

    def __init__(self) -> None:
        s = get_aws_settings()
        self._glue = boto3.client("glue", region_name=s.aws_region)
        self._settings = s

    def start_crawler(self, crawler_name: str | None = None) -> None:
        name = crawler_name or self._settings.glue_crawler_name
        self._glue.start_crawler(Name=name)

    def wait_for_crawler(self, crawler_name: str | None = None, poll_seconds: int = 10) -> str:
        """Poll until the crawler reaches READY state; return final state."""
        name = crawler_name or self._settings.glue_crawler_name
        while True:
            resp = self._glue.get_crawler(Name=name)
            state = resp["Crawler"]["State"]
            if state == "READY":
                return state
            time.sleep(poll_seconds)

    def start_job(self, job_name: str, arguments: dict[str, str] | None = None) -> str:
        """Trigger a Glue ETL job; return the job run ID."""
        resp = self._glue.start_job_run(
            JobName=job_name,
            Arguments=arguments or {},
        )
        return resp["JobRunId"]

    def get_job_status(self, job_name: str, run_id: str) -> str:
        resp = self._glue.get_job_run(JobName=job_name, RunId=run_id)
        return resp["JobRun"]["JobRunState"]


class S3SourceConnector(BaseSourceConnector):
    """
    Reads documents from Amazon S3.
    Supports .txt, .md, .pdf, and .html files.
    """

    def __init__(self, bucket: str | None = None, prefix: str = "") -> None:
        s = get_aws_settings()
        self._bucket = bucket or s.s3_bucket
        self._prefix = prefix
        self._s3 = boto3.client("s3", region_name=s.aws_region)

    def fetch(self) -> list[RawDocument]:
        paginator = self._s3.get_paginator("list_objects_v2")
        docs: list[RawDocument] = []

        for page in paginator.paginate(Bucket=self._bucket, Prefix=self._prefix):
            for obj in page.get("Contents", []):
                key: str = obj["Key"]
                if not any(key.endswith(ext) for ext in (".txt", ".md", ".pdf", ".html")):
                    continue

                raw = self._s3.get_object(Bucket=self._bucket, Key=key)["Body"].read()
                content = self._extract(key, raw)
                if not content:
                    continue

                docs.append(RawDocument(
                    id=hashlib.sha256(key.encode()).hexdigest(),
                    source=f"s3://{self._bucket}/{key}",
                    content=content,
                    metadata={"s3_key": key, "size": obj["Size"]},
                ))

        return docs

    def _extract(self, key: str, raw: bytes) -> str:
        if key.endswith(".pdf"):
            from pypdf import PdfReader
            import io
            return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(raw)).pages)
        if key.endswith(".html"):
            from bs4 import BeautifulSoup
            return BeautifulSoup(raw, "html.parser").get_text(separator="\n")
        return raw.decode("utf-8", errors="replace")
