"""
storage/data_lake/s3_store.py
Data lake abstraction over S3-compatible object storage.
Manages raw, processed, and archived document partitions.
"""
from __future__ import annotations

import io
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

import boto3
import pandas as pd


class DataPartition:
    RAW = "raw"
    PROCESSED = "processed"
    FINE_TUNING = "fine_tuning"
    EVAL = "eval"
    ARCHIVED = "archived"


@dataclass
class S3Object:
    key: str
    size_bytes: int
    last_modified: str
    metadata: dict[str, str]


class S3DataLake:
    def __init__(self, bucket: str, region: str = "us-east-1", prefix: str = "llmops"):
        self.bucket = bucket
        self.prefix = prefix
        self._s3 = boto3.client("s3", region_name=region)

    def _key(self, partition: str, filename: str, date: datetime | None = None) -> str:
        d = date or datetime.utcnow()
        return f"{self.prefix}/{partition}/year={d.year}/month={d.month:02d}/day={d.day:02d}/{filename}"

    def upload_json(self, data: list[dict] | dict, partition: str, filename: str) -> str:
        key = self._key(partition, filename)
        body = json.dumps(data, ensure_ascii=False, indent=2).encode()
        self._s3.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType="application/json")
        return f"s3://{self.bucket}/{key}"

    def upload_parquet(self, df: pd.DataFrame, partition: str, filename: str) -> str:
        key = self._key(partition, filename.replace(".parquet", "") + ".parquet")
        buf = io.BytesIO()
        df.to_parquet(buf, index=False, engine="pyarrow")
        buf.seek(0)
        self._s3.put_object(Bucket=self.bucket, Key=key, Body=buf.read(),
                            ContentType="application/octet-stream")
        return f"s3://{self.bucket}/{key}"

    def download_json(self, key: str) -> Any:
        obj = self._s3.get_object(Bucket=self.bucket, Key=key)
        return json.loads(obj["Body"].read())

    def download_parquet(self, key: str) -> pd.DataFrame:
        obj = self._s3.get_object(Bucket=self.bucket, Key=key)
        return pd.read_parquet(io.BytesIO(obj["Body"].read()))

    def list_partition(self, partition: str, prefix_filter: str = "") -> Iterator[S3Object]:
        full_prefix = f"{self.prefix}/{partition}/{prefix_filter}"
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=full_prefix):
            for obj in page.get("Contents", []):
                meta_resp = self._s3.head_object(Bucket=self.bucket, Key=obj["Key"])
                yield S3Object(
                    key=obj["Key"],
                    size_bytes=obj["Size"],
                    last_modified=obj["LastModified"].isoformat(),
                    metadata=meta_resp.get("Metadata", {}),
                )

    def move_to_archive(self, key: str) -> str:
        filename = Path(key).name
        new_key = self._key(DataPartition.ARCHIVED, filename)
        self._s3.copy_object(
            Bucket=self.bucket,
            CopySource={"Bucket": self.bucket, "Key": key},
            Key=new_key,
            StorageClass="GLACIER",
        )
        self._s3.delete_object(Bucket=self.bucket, Key=key)
        return f"s3://{self.bucket}/{new_key}"

    def apply_retention_policy(self, partition: str, max_days: int) -> int:
        """Delete objects older than max_days. Returns count deleted."""
        from datetime import timezone
        cutoff = datetime.now(timezone.utc).timestamp() - (max_days * 86400)
        deleted = 0
        for obj in self.list_partition(partition):
            ts = datetime.fromisoformat(obj.last_modified).timestamp()
            if ts < cutoff:
                self._s3.delete_object(Bucket=self.bucket, Key=obj.key)
                deleted += 1
        return deleted
