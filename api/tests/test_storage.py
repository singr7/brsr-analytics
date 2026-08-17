from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from api.app.core.config import Settings
from api.app.services.storage import (
    InstanceCredentials,
    LocalObjectStore,
    S3ObjectStore,
    object_store,
    raw_filing_key,
)


def _s3_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "object_store_backend": "s3",
        "filings_bucket": "brsrlens-filings-raw-test",
        "aws_region": "ap-south-1",
    }
    values.update(overrides)
    return Settings(**values)


class _MetadataStub:
    """Stands in for IMDSv2, recording how many times credentials were fetched."""

    def __init__(self, expires_in: timedelta = timedelta(hours=6)) -> None:
        self.fetches = 0
        self.expires_at = datetime.now(UTC) + expires_in

    def put(self, url: str, **_: Any) -> httpx.Response:
        assert url.endswith("/api/token")
        return httpx.Response(200, text="imds-token", request=httpx.Request("PUT", url))

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        # IMDSv2 refuses any request without the session token, which is what
        # keeps the metadata service out of reach of a plain SSRF.
        assert kwargs["headers"]["X-aws-ec2-metadata-token"] == "imds-token"
        request = httpx.Request("GET", url)
        if url.endswith("/security-credentials/"):
            return httpx.Response(200, text="brsrlens-prod-node", request=request)
        self.fetches += 1
        return httpx.Response(
            200,
            json={
                "AccessKeyId": "ASIAEXAMPLE",
                "SecretAccessKey": "instance-secret",
                "Token": "instance-token",
                "Expiration": self.expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            request=request,
        )


@pytest.fixture
def metadata(monkeypatch: pytest.MonkeyPatch) -> _MetadataStub:
    stub = _MetadataStub()
    monkeypatch.setattr(httpx, "put", stub.put)
    monkeypatch.setattr(httpx, "get", stub.get)
    return stub


def test_static_keys_take_precedence_over_the_instance_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_: Any, **__: Any) -> None:
        raise AssertionError("the metadata service must not be contacted when keys are configured")

    monkeypatch.setattr(httpx, "put", fail)
    monkeypatch.setattr(httpx, "get", fail)

    store = S3ObjectStore(
        _s3_settings(
            aws_access_key_id="AKIALOCAL",
            aws_secret_access_key="local-secret",
            aws_session_token=None,
        )
    )

    assert store.access_key == "AKIALOCAL"
    assert store.secret_key == "local-secret"
    assert store.session_token is None


def test_falls_back_to_instance_role_credentials(metadata: _MetadataStub) -> None:
    # Production ships no AWS keys: the node's IAM role is the only credential.
    store = S3ObjectStore(_s3_settings())

    assert store.access_key == "ASIAEXAMPLE"
    assert store.secret_key == "instance-secret"
    assert store.session_token == "instance-token"


def test_instance_credentials_are_cached_until_they_near_expiry() -> None:
    credentials = InstanceCredentials()
    stub = _MetadataStub()

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(httpx, "put", stub.put)
        patch.setattr(httpx, "get", stub.get)

        credentials.current()
        credentials.current()
        credentials.current()
        assert stub.fetches == 1, "valid credentials must not be re-fetched on every request"

        # Inside the refresh margin the cached values are treated as stale, so a
        # request is never signed with a token that lapses mid-flight.
        credentials._expires_at = datetime.now(UTC) + timedelta(minutes=1)
        credentials.current()
        assert stub.fetches == 2


def test_s3_construction_no_longer_requires_static_keys() -> None:
    # Constructing the store must not raise: on an instance the credentials are
    # resolved lazily, and raising here would break startup rather than a call.
    assert isinstance(object_store(_s3_settings()), S3ObjectStore)


def test_local_backend_is_still_the_default(tmp_path: Any) -> None:
    settings = Settings(object_store_local_root=str(tmp_path), filings_bucket="filings-raw")
    store = object_store(settings)

    assert isinstance(store, LocalObjectStore)
    uri = store.put(raw_filing_key("L12345MH2000PLC000001", 2025, "brsr.xml"), b"<x/>", "text/xml")
    assert uri == "s3://filings-raw/raw/L12345MH2000PLC000001/2025/brsr.xml"
    assert store.get(uri) == b"<x/>"
