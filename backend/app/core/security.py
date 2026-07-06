from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings

# argon2-cffi مستقیم به‌جای passlib (رهاشده) و PyJWT به‌جای python-jose (رهاشده).
# فرمت هش‌های قبلی (passlib[argon2]) همان فرمت استاندارد encoded آرگون۲ است و
# بدون مهاجرت قابل verify است.
_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def _create_token(
    subject: str,
    role: str,
    token_version: int,
    expires_delta: timedelta,
    token_type: str,
    jti: str | None = None,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "role": role,
        "tv": token_version,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if jti is not None:
        payload["jti"] = jti
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int, role: str, token_version: int) -> str:
    return _create_token(
        str(user_id),
        role,
        token_version,
        timedelta(minutes=settings.access_token_expire_minutes),
        "access",
    )


def create_refresh_token(user_id: int, role: str, token_version: int, jti: str) -> str:
    return _create_token(
        str(user_id),
        role,
        token_version,
        timedelta(days=settings.refresh_token_expire_days),
        "refresh",
        jti=jti,
    )


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
