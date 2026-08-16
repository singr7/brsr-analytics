from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from pydantic import ValidationError

from api.app.core.config import Settings
from api.app.services.auth import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_opaque_token,
    hash_password,
    opaque_token,
    verify_password,
)


def test_argon2_password_round_trip() -> None:
    password_hash = hash_password("CorrectHorseBatteryStaple")
    assert password_hash.startswith("$argon2")
    assert verify_password(password_hash, "CorrectHorseBatteryStaple")
    assert not verify_password(password_hash, "incorrect")
    assert not verify_password("legacy-placeholder", "anything")


def test_access_and_refresh_tokens_have_distinct_types() -> None:
    settings = Settings(
        jwt_secret="unit-test-secret-that-is-at-least-32-bytes", jwt_issuer="unit-tests"
    )
    user_id = uuid4()
    access, expires_in = create_access_token(settings, user_id)
    refresh, jti, family, expires_at = create_refresh_token(settings, user_id)

    assert expires_in == 15 * 60
    assert decode_token(settings, access, "access")["sub"] == str(user_id)
    refresh_claims = decode_token(settings, refresh, "refresh")
    assert refresh_claims["jti"] == str(jti)
    assert refresh_claims["family"] == str(family)
    assert expires_at > datetime.now(UTC) + timedelta(days=29)
    with pytest.raises(TokenError, match="wrong token type"):
        decode_token(settings, access, "refresh")


def test_expired_token_is_rejected() -> None:
    settings = Settings(
        jwt_secret="unit-test-secret-that-is-at-least-32-bytes", jwt_issuer="unit-tests"
    )
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "type": "access",
            "iss": settings.jwt_issuer,
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(TokenError, match="invalid or expired"):
        decode_token(settings, token, "access")


def test_opaque_tokens_are_random_and_stored_as_hashes() -> None:
    first, second = opaque_token(), opaque_token()
    assert first != second
    assert len(hash_opaque_token(first)) == 64
    assert hash_opaque_token(first) != hash_opaque_token(second)


def test_production_rejects_default_jwt_secret() -> None:
    # _env_file=None keeps the guard under test independent of a developer's local .env,
    # which would otherwise supply a strong secret and silently pass the assertion.
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(app_env="production", _env_file=None)


def test_production_rejects_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(app_env="production", jwt_secret="too-short", _env_file=None)


def _production_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "app_env": "production",
        "jwt_secret": "x" * 32,
        "auth_expose_verification_token": False,
        "llm_provider": "openai",
        "_env_file": None,
    }
    return Settings(**(base | overrides))  # type: ignore[arg-type]


def test_production_rejects_exposed_verification_token() -> None:
    with pytest.raises(ValidationError, match="AUTH_EXPOSE_VERIFICATION_TOKEN"):
        _production_settings(auth_expose_verification_token=True)


def test_production_rejects_fake_llm_provider() -> None:
    with pytest.raises(ValidationError, match="LLM_PROVIDER"):
        _production_settings(llm_provider="fake")


def test_production_accepts_a_fully_configured_deployment() -> None:
    assert _production_settings().app_env == "production"
