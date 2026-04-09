"""
Cloudflare R2 storage service.
Uses boto3 S3-compatible API with zero egress costs.
"""

import boto3
from botocore.config import Config

from app.config import settings

_s3_client = None


def get_r2_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            config=Config(
                signature_version="s3v4",
                region_name="auto",
            ),
        )
    return _s3_client


async def upload_to_r2(
    content: bytes,
    key: str,
    content_type: str = "application/pdf",
) -> str:
    """
    Upload a file to Cloudflare R2.
    Returns the R2 key for later retrieval.
    """
    client = get_r2_client()
    client.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
        Body=content,
        ContentType=content_type,
    )
    return key


async def get_presigned_url(key: str, expires_in: int = 900) -> str:
    """
    Generate a presigned URL for downloading a file from R2.
    Default expiry: 15 minutes.
    """
    client = get_r2_client()
    url = client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.R2_BUCKET_NAME,
            "Key": key,
        },
        ExpiresIn=expires_in,
    )
    return url


async def delete_from_r2(key: str) -> None:
    """Delete a file from R2."""
    client = get_r2_client()
    client.delete_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
    )


async def list_firm_files(firm_id: str, prefix: str = "") -> list[dict]:
    """List files for a specific firm in R2."""
    client = get_r2_client()
    full_prefix = f"{prefix}/{firm_id}/" if prefix else f"{firm_id}/"

    response = client.list_objects_v2(
        Bucket=settings.R2_BUCKET_NAME,
        Prefix=full_prefix,
    )

    files = []
    for obj in response.get("Contents", []):
        files.append({
            "key": obj["Key"],
            "size": obj["Size"],
            "last_modified": str(obj["LastModified"]),
        })
    return files
