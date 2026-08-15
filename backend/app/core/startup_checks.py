"""گاردهای زمان راه‌اندازی که به دیتابیس نیاز دارند.

گاردهای صرفاً پیکربندی‌ای (JWT_SECRET_KEY، CORS، PUBLIC_BASE_URL، SEED_DEMO_DATA)
در core/config.py هنگام ساخت Settings اجرا می‌شوند. آن‌چه این‌جاست به *وضعیت
دیتابیس* نگاه می‌کند، پس تا باز شدن یک session قابل بررسی نیست.
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.demo_data import DEMO_PASSWORD, DEMO_USERNAMES
from app.core.security import verify_password
from app.models.user import User

logger = logging.getLogger("dbspulse.startup")


def find_active_demo_accounts(db: Session) -> list[str]:
    """کاربران فعالی که هنوز رمز دموی منتشرشده را دارند.

    فقط نام‌های کاربری شناخته‌شدهٔ دمو بررسی می‌شوند: verify آرگون۲ عمداً کند است
    و اسکن کل جدول کاربران، استارت‌آپ را به‌ازای هر کاربر ~۱۰۰ms کند می‌کند. مسیری
    که این حساب‌ها را می‌سازد مایگریشن seed است و دقیقاً همین نام‌ها را می‌سازد.
    """
    rows = db.execute(
        select(User.username, User.password_hash).where(
            User.username.in_(DEMO_USERNAMES), User.is_active.is_(True)
        )
    ).all()
    return sorted(username for username, hashed in rows if verify_password(DEMO_PASSWORD, hashed))


def assert_no_demo_credentials() -> None:
    """در production با حساب دموی فعال بالا نمی‌آییم.

    fail-closed است: اگر دیتابیس در دسترس نباشد خطا بالا می‌رود و کانتینر ری‌استارت
    می‌خورد — «نتوانستم بررسی کنم» نباید به «پس فرض می‌گیرم امن است» تبدیل شود.
    """
    if settings.environment != "production":
        return

    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        offenders = find_active_demo_accounts(db)
    finally:
        db.close()

    if offenders:
        raise RuntimeError(
            "این حساب‌ها هنوز رمز دموی منتشرشده در مخزن را دارند و فعال‌اند: "
            + "، ".join(offenders)
            + ". در محیط production اجرا نمی‌شویم. رمزشان را عوض کنید یا "
            "غیرفعالشان کنید (مایگریشن a1d7f4e9b602 همین کار را می‌کند)."
        )

    logger.info("startup check: no active demo credentials")
