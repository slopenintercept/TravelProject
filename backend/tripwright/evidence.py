"""Evidence snapshots: every results page is saved so each price links back to proof.

Uploads to Akamai Object Storage when OBJ_* is configured, otherwise writes under
DATA_DIR/evidence (served by the API at /evidence).
"""

from __future__ import annotations

import asyncio
import re
import time

from botocore.exceptions import ClientError

from . import config

LOCAL_DIR = config.DATA_DIR / "evidence"
_client = None


def _s3():
    global _client
    if _client is None:
        import boto3

        _client = boto3.client(
            "s3",
            endpoint_url=f"https://{config.OBJ_ENDPOINT.removeprefix('https://')}",
            aws_access_key_id=config.OBJ_ACCESS_KEY,
            aws_secret_access_key=config.OBJ_SECRET_KEY,
        )
    return _client


def _put(key: str, data: bytes, content_type: str) -> str:
    if config.OBJ_BUCKET and config.OBJ_ENDPOINT:
        target = {"Bucket": config.OBJ_BUCKET, "Key": key}
        try:
            # public-read so the review card's evidence link opens without signing.
            _s3().put_object(**target, Body=data, ContentType=content_type, ACL="public-read")
        except ClientError:
            # The access key may not be allowed to set ACLs: keep the object private and sign a link.
            _s3().put_object(**target, Body=data, ContentType=content_type)
            return _s3().generate_presigned_url("get_object", Params=target, ExpiresIn=7 * 24 * 3600)
        return f"https://{config.OBJ_BUCKET}.{config.OBJ_ENDPOINT.removeprefix('https://')}/{key}"
    path = LOCAL_DIR / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return f"/evidence/{key}"


async def save(label: str, data: bytes, ext: str = "png") -> str:
    """Store one snapshot and return its URL."""
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:60]
    key = f"{time.strftime('%Y%m%d')}/{slug}-{int(time.time() * 1000) % 10_000_000}.{ext}"
    content_type = {"png": "image/png", "txt": "text/plain; charset=utf-8"}[ext]
    return await asyncio.to_thread(_put, key, data, content_type)
