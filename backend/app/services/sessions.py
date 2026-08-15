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


def create_session(
    db: Session,
    user_id: int,
    *,
    user_agent: str | None = None,
    ip: str | None = None,
) -> str:
    """نشست جدید می‌سازد و jti آن را برمی‌گرداند.

    user_agent و ip فقط برای این‌اند که خودِ کاربر بتواند نشست‌هایش را تشخیص بدهد
    (P2-06). اختیاری‌اند تا مسیرهایی که این اطلاعات را در دست ندارند مجبور به
    ساختن مقدار جعلی نشوند — «نامشخص» صادقانه‌تر از یک حدس است.
    """
    jti = uuid.uuid4().hex
    now = _now()
    db.add(
        AuthSession(
            user_id=user_id,
            jti=jti,
            expires_at=now + timedelta(days=settings.refresh_token_expire_days),
            # رشتهٔ user-agent بلند است و طول ستون محدود؛ بریدن بهتر از خطای درج است
            user_agent=(user_agent or None) and user_agent[:400],
            ip=ip,
            last_used_at=now,
        )
    )
    return jti


def active_sessions(db: Session, user_id: int) -> list[AuthSession]:
    """نشست‌های زندهٔ کاربر: نه باطل‌شده، نه منقضی، نه چرخیده.

    نشستِ چرخیده (rotated_at پر است) دیگر قابل استفاده نیست — نمایشش فقط فهرست
    را با ردیف‌های مرده پر می‌کرد و کاربر را می‌ترساند.
    """
    now = _now()
    return list(
        db.scalars(
            select(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.rotated_at.is_(None),
                AuthSession.expires_at > now,
            )
            .order_by(AuthSession.last_used_at.desc().nullslast())
        )
    )


def rotate_session(
    db: Session,
    user_id: int,
    jti: str,
    *,
    user_agent: str | None = None,
    ip: str | None = None,
) -> str | None:
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

    # نشستِ جانشین، هویتِ نمایشیِ نشست قبلی را به ارث می‌برد مگر اینکه درخواست
    # تازه چیز بهتری بدهد. بدون این، هر refresh یک ردیف «نامشخص» می‌ساخت و فهرست
    # نشست‌ها بعد از یک روز کاملاً ناخوانا می‌شد.
    new_jti = create_session(
        db,
        user_id,
        user_agent=user_agent or session.user_agent,
        ip=ip or session.ip,
    )
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
