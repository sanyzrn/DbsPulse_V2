from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# اندازهٔ استخر عمداً و صریح تنظیم شده است، نه با پیش‌فرض (P2-05) — دلیلِ هر عدد
# در core/config.py کنار خودش نوشته شده. `pool_pre_ping` هم می‌ماند: اتصالی که
# سمت سرور بسته شده باید پیش از استفاده تشخیص داده شود، نه وسط تراکنش.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout_seconds,
    pool_recycle=settings.db_pool_recycle_seconds,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def pool_stats() -> dict[str, int]:
    """وضعیت لحظه‌ای استخر، برای سنجه‌ها و readiness.

    اشباع استخر از بیرون شبیه «دیتابیس کند شده» دیده می‌شود، در حالی‌که دیتابیس
    بی‌کار است و درخواست‌ها فقط در صف اتصال ایستاده‌اند. بدون این عدد، تشخیص این
    دو از هم ممکن نیست.
    """
    pool = engine.pool
    checked_out = pool.checkedout()
    overflow = pool.overflow()
    return {
        # اتصال‌هایی که همین حالا دست یک درخواست‌اند
        "checked_out": checked_out,
        # اتصال‌های آزادِ آمادهٔ استفاده
        "available": pool.checkedin(),
        # چند اتصالِ «سرریز» (بیش از pool_size) باز است؛ منفی یعنی هنوز سرریزی نبوده
        "overflow": overflow,
        # سقف مطلق: از این بیشتر، درخواست‌ها منتظر می‌مانند و بعد timeout می‌خورند
        "capacity": settings.db_pool_size + settings.db_max_overflow,
    }


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
