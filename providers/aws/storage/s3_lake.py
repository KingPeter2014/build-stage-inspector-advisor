"""
providers/aws/storage/s3_lake.py
Amazon S3 data lake — AbstractDataLake implementation.
"""
from __future__ import annotations

import json
from io import BytesIO

import boto3

from core.interfaces.data_lake import AbstractDataLake, LakeObject
from providers.aws.config.settings import get_aws_settings


class AWSS3DataLake(AbstractDataLake):
    """AbstractDataLake backed by Amazon S3. Object keys: {partition}/{key}."""

    def __init__(self, bucket: str | None = None) -> None:
        s = get_aws_settings()
        self._bucket = bucket or s.s3_bucket
        self._s3 = boto3.client("s3", region_name=s.aws_region)

    def _full_key(self, key: str, partition: str = "") -> str:
        return f"{partition}/{key}" if partition else key

    def upload_json(self, data: dict | list, key: str, partition: str = "raw") -> str:
        full_key = self._full_key(key, partition)
        payload = json.dumps(data, default=str).encode()
        self._s3.put_object(Bucket=self._bucket, Key=full_key, Body=payload,
                             ContentType="application/json")
        return f"s3://{self._bucket}/{full_key}"

    def upload_bytes(self, data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        self._s3.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)
        return f"s3://{self._bucket}/{key}"

    def download_json(self, key: str) -> dict | list:
        resp = self._s3.get_object(Bucket=self._bucket, Key=key)
        return json.loads(resp["Body"].read())

    def download_bytes(self, key: str) -> bytes:
        return self._s3.get_object(Bucket=self._bucket, Key=key)["Body"].read()

    def list_partition(self, partition: str, prefix: str = "") -> list[LakeObject]:
        full_prefix = self._full_key(prefix, partition) if prefix else f"{partition}/"
        paginator = self._s3.get_paginator("list_objects_v2")
        objects: list[LakeObject] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=full_prefix):
            for obj in page.get("Contents", []):
                objects.append(LakeObject(
                    key=obj["Key"],
                    size_bytes=obj["Size"],
                    last_modified=obj["LastModified"].isoformat(),
                    partition=partition,
                ))
        return objects

    def delete(self, key: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=key)
