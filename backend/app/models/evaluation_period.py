from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, func
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
