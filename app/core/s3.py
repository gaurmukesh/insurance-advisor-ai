import boto3
from app.core.config import settings

_s3_client = None


def _get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=settings.AWS_REGION or None)
    return _s3_client


def list_policy_pdf_keys() -> list[str]:
    """All .pdf keys under POLICIES_S3_BUCKET/POLICIES_S3_PREFIX, sorted."""
    client = _get_s3_client()
    paginator = client.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=settings.POLICIES_S3_BUCKET, Prefix=settings.POLICIES_S3_PREFIX):
        for obj in page.get("Contents", []):
            if obj["Key"].lower().endswith(".pdf"):
                keys.append(obj["Key"])
    return sorted(keys)


def fetch_pdf_bytes(key: str) -> bytes:
    client = _get_s3_client()
    response = client.get_object(Bucket=settings.POLICIES_S3_BUCKET, Key=key)
    return response["Body"].read()


def put_pdf_bytes(key: str, content: bytes) -> None:
    client = _get_s3_client()
    client.put_object(Bucket=settings.POLICIES_S3_BUCKET, Key=key, Body=content, ContentType="application/pdf")
