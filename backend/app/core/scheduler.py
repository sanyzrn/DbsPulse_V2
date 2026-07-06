"""زمان‌بند سبک درون‌پروسه برای اجرای دوره‌ای sweep های اعلان.

عمداً وابستگی جدید (Celery/APScheduler) اضافه نمی‌کنیم؛ یک حلقه asyncio در lifespan
کافی است. کار همگام دیتابیس در threadpool اجرا می‌شود تا event loop بلاک نشود.
برای استقرار چند-instance بعداً باید به worker/queue مشترک (مثلاً arq+Redis) مهاجرت کرد
تا هر instance جداگانه اجرا نکند.
"""
import asyncio
import contextlib
import logging

from app.core.config import settings

logger = logging.getLogger("dbspulse.scheduler")


def _run_sweeps_sync() -> dict[str, int]:
    from app.db.session import SessionLocal
    from app.services.scheduled import run_all_sweeps

    db = SessionLocal()
    try:
        return run_all_sweeps(db)
    finally:
        db.close()


async def _scheduler_loop() -> None:
    interval = settings.scheduler_interval_seconds
    logger.info("scheduler started (interval=%ss)", interval)
    while True:
        try:
            summary = await asyncio.to_thread(_run_sweeps_sync)
            if any(summary.values()):
                logger.info("sweep created notifications: %s", summary)
        except Exception:
            logger.exception("scheduled sweep failed")
        await asyncio.sleep(interval)


@contextlib.asynccontextmanager
async def lifespan(app):
    task: asyncio.Task | None = None
    if settings.enable_scheduler:
        task = asyncio.create_task(_scheduler_loop())
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
