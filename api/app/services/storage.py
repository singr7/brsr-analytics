from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Protocol
from urllib.parse import quote, urlsplit

import httpx

from api.app.core.config import Settings


class ObjectStore(Protocol):
    def put(self, key: str, content: bytes, content_type: str) -> str: ...

    def get(self, uri: str) -> bytes: ...


def raw_filing_key(cin: str, fy: int, filename: str) -> str:
    safe_name = Path(filename).name
    if not safe_name or safe_name in {".", ".."}:
        raise ValueError("A valid filename is required")
    return str(PurePosixPath("raw", cin, str(fy), safe_name))


class LocalObjectStore:
    def __init__(self, root: str, bucket: str) -> None:
        self.root = Path(root).resolve()
        self.bucket = bucket

    def put(self, key: str, content: bytes, content_type: str) -> str:
        del content_type
        target = (self.root / self.bucket / key).resolve()
        if self.root not in target.parents:
            raise ValueError("Object key escapes storage root")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return f"s3://{self.bucket}/{key}"

    def get(self, uri: str) -> bytes:
        prefix = f"s3://{self.bucket}/"
        if not uri.startswith(prefix):
            raise ValueError("Object URI does not belong to this bucket")
        target = (self.root / self.bucket / uri.removeprefix(prefix)).resolve()
        if self.root not in target.parents:
            raise ValueError("Object URI escapes storage root")
        return target.read_bytes()


class S3ObjectStore:
    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.filings_bucket
        self.region = settings.aws_region
        self.endpoint = settings.s3_endpoint_url
        self.access_key = settings.aws_access_key_id
        self.secret_key = settings.aws_secret_access_key
        self.session_token = settings.aws_session_token
        if not self.access_key or not self.secret_key:
            raise ValueError("S3 backend requires AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")

    def put(self, key: str, content: bytes, content_type: str) -> str:
        encoded_key = quote(key, safe="/")
        url = (
            f"{self.endpoint.rstrip('/')}/{self.bucket}/{encoded_key}"
            if self.endpoint
            else f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{encoded_key}"
        )
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        payload_hash = hashlib.sha256(content).hexdigest()
        parsed = urlsplit(url)
        headers = {
            "content-type": content_type,
            "host": parsed.netloc,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
            "x-amz-server-side-encryption": "AES256",
        }
        if self.session_token:
            headers["x-amz-security-token"] = self.session_token
        signed_names = ";".join(sorted(headers))
        canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in sorted(headers))
        canonical_request = "\n".join(
            ["PUT", parsed.path, "", canonical_headers, signed_names, payload_hash]
        )
        scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                scope,
                hashlib.sha256(canonical_request.encode()).hexdigest(),
            ]
        )
        signature = hmac.new(
            self._signing_key(date_stamp), string_to_sign.encode(), hashlib.sha256
        ).hexdigest()
        headers["authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={self.access_key}/{scope}, "
            f"SignedHeaders={signed_names}, Signature={signature}"
        )
        response = httpx.put(url, content=content, headers=headers, timeout=60)
        response.raise_for_status()
        return f"s3://{self.bucket}/{key}"

    def get(self, uri: str) -> bytes:
        prefix = f"s3://{self.bucket}/"
        if not uri.startswith(prefix):
            raise ValueError("Object URI does not belong to this bucket")
        encoded_key = quote(uri.removeprefix(prefix), safe="/")
        url = (
            f"{self.endpoint.rstrip('/')}/{self.bucket}/{encoded_key}"
            if self.endpoint
            else f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{encoded_key}"
        )
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        payload_hash = hashlib.sha256(b"").hexdigest()
        parsed = urlsplit(url)
        headers = {
            "host": parsed.netloc,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }
        if self.session_token:
            headers["x-amz-security-token"] = self.session_token
        signed_names = ";".join(sorted(headers))
        canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in sorted(headers))
        canonical_request = "\n".join(
            ["GET", parsed.path, "", canonical_headers, signed_names, payload_hash]
        )
        scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                scope,
                hashlib.sha256(canonical_request.encode()).hexdigest(),
            ]
        )
        signature = hmac.new(
            self._signing_key(date_stamp), string_to_sign.encode(), hashlib.sha256
        ).hexdigest()
        headers["authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={self.access_key}/{scope}, "
            f"SignedHeaders={signed_names}, Signature={signature}"
        )
        response = httpx.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        return response.content

    def _signing_key(self, date_stamp: str) -> bytes:
        date_key = hmac.new(
            f"AWS4{self.secret_key}".encode(), date_stamp.encode(), hashlib.sha256
        ).digest()
        region_key = hmac.new(date_key, self.region.encode(), hashlib.sha256).digest()
        service_key = hmac.new(region_key, b"s3", hashlib.sha256).digest()
        return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()


def object_store(settings: Settings) -> ObjectStore:
    if settings.object_store_backend == "local":
        return LocalObjectStore(settings.object_store_local_root, settings.filings_bucket)
    if settings.object_store_backend == "s3":
        return S3ObjectStore(settings)
    raise ValueError(f"Unsupported object store backend: {settings.object_store_backend}")
