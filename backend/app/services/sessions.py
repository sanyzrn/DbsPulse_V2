import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth_session import AuthSession

# مهلت کوتاهی که در آن استفاده دوباره از توکنِ تازه‌چرخیده «سرقت» حساب نمی‌شود؛
# دو تب هم‌زمان که هر دو refresh می‌زنند نباید کاربر را از سیستم بیرون بیندازند.
ROTATION_GRACE_SECONDS = 60


class RefreshReuseError(Exception):
    """استفاده دوباره از refresh token چرخیده/باطل‌شده — نشانه احتمالی سرقت توکن."""


def _now() -> datetime:
    return datetime.now(UTC)


def create_session(db: Session, user_id: int) -> str:
    """نشست جدید می‌سازد و jti آن را برمی‌گرداند."""
    jti = uuid.uuid4().hex
    db.add(
        AuthSession(
            user_id=user_id,
            jti=jti,
            expires_at=_now() + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    return jti


def rotate_session(db: Session, user_id: int, jti: str) -> str | None:
    """اعتبارسنجی و چرخش نشست.

    خروجی: jti جدید، یا None اگر توکن در مهلت grace دوباره استفاده شده باشد
    (در این حالت access token صادر می‌شود ولی کوکی عوض نمی‌شود).
    خطا: RefreshReuseError برای توکن باطل/سرقتی — تمام نشست‌های کاربر باطل می‌شوند.
    """
    session = db.scalar(select(AuthSession).where(AuthSession.jti == jti))
    now = _now()

    if (
        session is None
        or session.user_id != user_id
        or session.revoked_at is not None
        or session.expires_at <= now
    ):
        revoke_all_for_user(db, user_id)
        raise RefreshReuseError

    if session.rotated_at is not None:
        if (now - session.rotated_at).total_seconds() <= ROTATION_GRACE_SECONDS:
            return None
        # استفاده دوباره خارج از مهلت → کل خانواده نشست‌ها باطل می‌شود
        revoke_all_for_user(db, user_id)
        raise RefreshReuseError

    new_jti = create_session(db, user_id)
    session.rotated_at = now
    session.replaced_by_jti = new_jti
    return new_jti


def revoke_session(db: Session, jti: str) -> None:
    session = db.scalar(select(AuthSession).where(AuthSession.jti == jti))
    if session is not None and session.revoked_at is None:
        session.revoked_at = _now()


def revoke_all_for_user(db: Session, user_id: int) -> None:
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
