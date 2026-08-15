from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import PeriodStatus


class EvaluationPeriod(Base):
    """دوره (کمپین) ارزیابی: HR یک دوره نام‌دار باز می‌کند؛ ارزیابی‌های جدید به‌صورت
    خودکار به دوره باز برچسب می‌خورند و پیشرفت تکمیل دوره قابل رهگیری است.

    قانون v1: در هر لحظه حداکثر یک دوره باز وجود دارد (ایندکس یکتای جزئی در دیتابیس)."""

    __tablename__ = "evaluation_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PeriodStatus] = mapped_column(
        Enum(PeriodStatus, name="period_status", values_callable=lambda e: [m.value for m in e]),
        default=PeriodStatus.open,
        nullable=False,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # قانون «حداکثر یک دورهٔ باز» — با ایندکس یکتای جزئی، نه با بررسی در کد.
        # بررسی در کد در برابر دو درخواست هم‌زمان بی‌فایده است: هر دو می‌بینند
        # دورهٔ بازی نیست و هر دو یکی می‌سازند.
        #
        # اعلامش این‌جا حیاتی است: تا امروز فقط در مایگریشن وجود داشت، و
        # `alembic revision --autogenerate` آن را «اضافی» می‌دید و DROP پیشنهاد
        # می‌داد. یعنی هر کسی که یک‌بار autogenerate را بدون خواندنِ خروجی اجرا
        # می‌کرد، این گارد را بی‌صدا حذف می‌کرد.
        Index(
            "uq_single_open_period",
            "status",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )
