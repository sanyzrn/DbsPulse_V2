from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SchedulerRun(Base):
    """تاریخچهٔ اجرای کارهای زمان‌بندی‌شده.

    بدون این، «آیا یادآوری‌ها اجرا شدند؟» فقط از روی لاگ کانتینر قابل جواب بود —
    و اگر زمان‌بند اصلاً روشن نبود، هیچ نشانهٔ منفی‌ای هم وجود نداشت. سکوت از
    «سالم» قابل تشخیص نبود.
    """

    __tablename__ = "scheduler_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # succeeded | failed | skipped_locked  (skipped یعنی instance دیگری داشت اجرا می‌کرد)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    # چه کسی راهش انداخت: scheduler یا manual
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    # تعداد اعلان‌های ساخته‌شده به تفکیک هر sweep
    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ایندکس‌ها در مایگریشن‌ها ساخته شده‌اند و تا امروز روی مدل اعلام نشده بودند،
    # پس `alembic revision --autogenerate` آن‌ها را «اضافی» می‌دید و DROP پیشنهاد
    # می‌داد. اعلامشان این‌جا یعنی autogenerate واقعیتِ دیتابیس را می‌بیند.
    __table_args__ = (
        Index("ix_scheduler_runs_started_at", "started_at"),
    )
