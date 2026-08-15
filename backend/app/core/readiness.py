"""بررسی‌های آمادگی که واقعاً چیزی را ثابت می‌کنند (P1-12).

«اتصال دیتابیس برقرار است» تقریباً همیشه درست است و تقریباً هیچ‌وقت آن چیزی
نیست که خراب می‌شود. دو چیزی که واقعاً خراب می‌شوند و از بیرون دیده نمی‌شوند:

* کانتینر بالا آمده ولی مایگریشن‌ها اجرا نشده‌اند. برنامه سالم به‌نظر می‌رسد و
  روی اولین درخواستی که ستون تازه را می‌خواهد خطا می‌دهد.
* زمان‌بند مدتی است اجرا نشده، پس یادآوری‌های قرارداد و SLA بی‌صدا قطع شده‌اند.
"""
from datetime import datetime
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.scheduler_run import SchedulerRun

_BACKEND_ROOT = Path(__file__).resolve().parents[2]

# نسخهٔ head از روی فایل‌های مایگریشن یک‌بار خوانده و کش می‌شود: در زمان اجرا
# تغییر نمی‌کند و خواندن دوبارهٔ دایرکتوری در هر readiness probe هدر است.
_cached_head: str | None | tuple[None] = (None,)


def expected_head() -> str | None:
    """آخرین نسخهٔ مایگریشن طبق کدِ همین استقرار."""
    global _cached_head
    if _cached_head != (None,):
        return _cached_head  # type: ignore[return-value]
    try:
        config = Config(str(_BACKEND_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
        _cached_head = ScriptDirectory.from_config(config).get_current_head()
    except Exception:  # noqa: BLE001 — نبودِ فایل‌های alembic نباید readiness را بترکاند
        _cached_head = None
    return _cached_head  # type: ignore[return-value]


def migration_state(db: Session) -> tuple[str | None, str | None]:
    """(نسخهٔ مورد انتظار طبق کد، نسخهٔ اعمال‌شده در دیتابیس)."""
    try:
        applied = db.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
    except Exception:  # noqa: BLE001 — جدول نبودن یعنی هیچ مایگریشنی اجرا نشده
        applied = None
    return expected_head(), applied


def last_successful_sweep(db: Session) -> datetime | None:
    """زمان آخرین اجرای *موفق* کارهای زمان‌بندی‌شده (تاریخچه از P0-08).

    فقط `succeeded` حساب می‌شود. «skipped_locked» یعنی instance دیگری قفل رهبری
    را داشت — این نه موفقیت است نه شکست، و اگر موفقیت حساب می‌شد، خوشه‌ای که
    همهٔ اعضایش رد می‌کنند برای همیشه «تازه» به‌نظر می‌رسید.
    """
    try:
        return db.scalar(
            select(SchedulerRun.finished_at)
            .where(SchedulerRun.status == "succeeded")
            .order_by(SchedulerRun.finished_at.desc())
            .limit(1)
        )
    except Exception:  # noqa: BLE001
        return None
