"""اجرای «دقیقاً یک‌بار» کارهای زمان‌بندی‌شده + تاریخچهٔ اجرا (P0-08).

زمان‌بند یک حلقهٔ asyncio داخل خود پروسهٔ وب است. با یک instance مشکلی ندارد، ولی
با دو replica هر دو هم‌زمان جارو می‌زنند: اعلان تکراری، کار دوباره، و در بدترین
حالت شرایط رقابتی روی همان ردیف‌ها.

راه‌حل بدون سرویس جدید: قفل توصیه‌ای خودِ Postgres. `pg_try_advisory_lock` بلافاصله
برمی‌گردد؛ هر instance که قفل را نگرفت می‌داند رهبر نیست و رد می‌شود. قفل به session
گره خورده است، پس اگر آن instance کرش کند قفل خودبه‌خود آزاد می‌شود — برخلاف یک
ردیف قفلِ دستی در جدول که با کرش، برای همیشه قفل می‌ماند.

هر اجرا (موفق، ناموفق، یا ردشده) در scheduler_runs ثبت می‌شود، چون بدون تاریخچه
«اجرا شد و چیزی نبود» از «اصلاً اجرا نشد» قابل تشخیص نیست.
"""
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.metrics import sweep_runs
from app.models.scheduler_run import SchedulerRun

logger = logging.getLogger("dbspulse.scheduler")

# شناسهٔ دلخواه ولی ثابت برای قفل توصیه‌ای. فضای نام قفل‌ها در کل دیتابیس مشترک است،
# پس عدد باید یکتا و ثابت بماند.
_SWEEP_LOCK_KEY = 815_243_907


def _acquire_leader_lock(db: Session) -> bool:
    return bool(db.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": _SWEEP_LOCK_KEY}))


def _release_leader_lock(db: Session) -> None:
    db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _SWEEP_LOCK_KEY})


def run_sweeps_once(
    db: Session, runner: Callable[[Session], dict[str, int]], *, trigger: str
) -> SchedulerRun:
    """جاروها را زیر قفل رهبری اجرا می‌کند و نتیجه را ثبت می‌کند.

    اگر instance دیگری قفل را دارد، وضعیت skipped_locked ثبت می‌شود و هیچ کاری
    انجام نمی‌شود — این «خطا» نیست، رفتار درست replica غیر-رهبر است.
    """
    if not _acquire_leader_lock(db):
        logger.info("sweep skipped: another instance holds the leader lock")
        sweep_runs.labels(outcome="skipped_locked").inc()
        run = SchedulerRun(status="skipped_locked", trigger=trigger, finished_at=datetime.now(UTC))
        db.add(run)
        db.commit()
        return run

    run = SchedulerRun(status="running", trigger=trigger)
    db.add(run)
    db.flush()
    try:
        summary = runner(db)
        run.status = "succeeded"
        sweep_runs.labels(outcome="succeeded").inc()
        run.summary = summary
        if any(summary.values()):
            logger.info("sweep created notifications: %s", summary)
    except Exception as exc:
        db.rollback()
        # ردیف اجرا باید حتی وقتی کار شکست خورده باقی بماند، وگرنه شکست بی‌صدا می‌شود.
        sweep_runs.labels(outcome="failed").inc()
        run = SchedulerRun(status="failed", trigger=trigger, error=str(exc)[:2000])
        db.add(run)
        logger.exception("scheduled sweep failed")
        raise
    finally:
        run.finished_at = datetime.now(UTC)
        db.add(run)
        db.commit()
        _release_leader_lock(db)
    return run


def recent_runs(db: Session, limit: int = 20) -> list[SchedulerRun]:
    return list(
        db.scalars(select(SchedulerRun).order_by(SchedulerRun.started_at.desc()).limit(limit))
    )
