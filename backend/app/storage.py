# backend/app/storage.py
from __future__ import annotations

import os
from typing import Optional
import boto3
from botocore.client import Config

from .config import settings

_s3 = None

def _client():
    global _s3
    if _s3 is None:
        _s3 = boto3.client(
            "s3",
            endpoint_url=settings.MINIO_ENDPOINT,
            aws_access_key_id=settings.MINIO_ROOT_USER,
            aws_secret_access_key=settings.MINIO_ROOT_PASSWORD,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
    return _s3

def put_object_bytes(key: str, data: bytes, content_type: str):
    _client().put_object(
        Bucket=settings.MINIO_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
    )

def get_object_bytes(key: str) -> bytes:
    r = _client().get_object(Bucket=settings.MINIO_BUCKET, Key=key)
    return r["Body"].read()

# ✅ 누락 보강: video_transcode.py에서 필요
def put_object_file(key: str, local_path: str, content_type: str):
    with open(local_path, "rb") as f:
        put_object_bytes(key, f.read(), content_type)