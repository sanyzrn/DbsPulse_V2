"""lifespan اپلیکیشن + زمان‌بند سبک درون‌پروسه برای اجرای دوره‌ای sweep های اعلان.

عمداً وابستگی جدید (Celery/APScheduler) اضافه نمی‌کنیم؛ یک حلقه asyncio در lifespan
کافی است. کار همگام دیتابیس در threadpool اجرا می‌شود تا event loop بلاک نشود.
برای استقرار چند-instance بعداً باید به worker/queue مشترک (مثلاً arq+Redis) مهاجرت کرد
تا هر instance جداگانه اجرا نکند.

lifespan علاوه بر زمان‌بند، گاردهای استارت‌آپِ وابسته به دیتابیس را هم اجرا می‌کند
(core/startup_checks.py) — پیش از این‌که اپ اولین درخواست را بپذیرد.
"""
import asyncio
import contextlib
import logging

from app.core.config import settings

logger = logging.getLogger("dbspulse.scheduler")


def _run_sweeps_sync() -> None:
    from app.db.session import SessionLocal
    from app.services.scheduled import run_all_sweeps
    from app.services.scheduler_lock import run_sweeps_once

    db = SessionLocal()
    try:
        # قفل رهبری داخل run_sweeps_once گرفته می‌شود: با چند replica فقط یکی
        # واقعاً جارو می‌زند و بقیه یک ردیف skipped_locked ثبت می‌کنند.
        run_sweeps_once(db, run_all_sweeps, trigger="scheduler")
    finally:
        db.close()


async def _scheduler_loop() -> None:
    interval = settings.scheduler_interval_seconds
    logger.info("scheduler started (interval=%ss)", interval)
    while True:
        try:
            await asyncio.to_thread(_run_sweeps_sync)
        except Exception:
            # لاگ و ثبت در scheduler_runs داخل run_sweeps_once انجام شده؛ این‌جا فقط
            # نمی‌گذاریم یک شکست، حلقه را برای همیشه بکشد.
            logger.exception("scheduler iteration failed; continuing")
        await asyncio.sleep(interval)


def _ensure_bootstrap_admin() -> None:
    if not settings.bootstrap_admin:
        return
    from app.db.session import SessionLocal
    from app.services.bootstrap_admin import ensure_bootstrap_admin

    with SessionLocal() as db:
        ensure_bootstrap_admin(db)
        db.commit()


def _load_integration_settings() -> None:
    from app.db.session import SessionLocal
    from app.services.integrations import refresh

    with SessionLocal() as db:
        refresh(db)


@contextlib.asynccontextmanager
async def lifespan(app):
    from app.core.startup_checks import assert_no_demo_credentials

    await asyncio.to_thread(assert_no_demo_credentials)
    # سامانه‌ای که بالا بیاید و هیچ‌کس نتواند واردش شود، بالا نیامده. اگر حسابِ
    # مدیری نباشد — نصبِ تازه، یا قفل‌شدن پس از غیرفعال‌شدنِ تنها مدیر — این‌جا
    # یکی ساخته می‌شود و رمزِ موقتش یک بار در لاگ می‌آید.
    await asyncio.to_thread(_ensure_bootstrap_admin)
    # تنظیمات ارسال بیرونی که از پنل ذخیره شده‌اند باید پیش از اولین ارسال روی
    # `settings` بنشینند. بدون این، تا اولین ذخیرهٔ بعدی، مقدارهای `.env` اثر
    # داشتند — یعنی تنظیماتِ پنل بعد از هر ری‌استارت بی‌صدا از کار می‌افتاد.
    await asyncio.to_thread(_load_integration_settings)

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
