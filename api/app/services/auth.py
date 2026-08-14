import hashlib
import secrets
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Any
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from api.app.core.config import Settings

_hasher = PasswordHasher()


class TokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def opaque_token() -> str:
    return secrets.token_urlsafe(32)


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(settings: Settings, user_id: UUID) -> tuple[str, int]:
    now = datetime.now(UTC)
    lifetime = timedelta(minutes=settings.access_token_minutes)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + lifetime,
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256"), int(
        lifetime.total_seconds()
    )


def create_refresh_token(
    settings: Settings, user_id: UUID, family_id: UUID | None = None
) -> tuple[str, UUID, UUID, datetime]:
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=settings.refresh_token_days)
    jti = uuid4()
    family = family_id or uuid4()
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": expires_at,
        "jti": str(jti),
        "family": str(family),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256"), jti, family, expires_at


def decode_token(settings: Settings, token: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=["HS256"], issuer=settings.jwt_issuer
        )
    except jwt.PyJWTError as exc:
        raise TokenError("invalid or expired token") from exc
    if payload.get("type") != expected_type:
        raise TokenError("wrong token type")
    return payload


def send_email(settings: Settings, recipient: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
        smtp.send_message(message)
