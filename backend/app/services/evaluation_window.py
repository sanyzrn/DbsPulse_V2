"""پنجرهٔ زمانی ثبت ارزیابی که منابع انسانی در «دوره‌ها» تعیین می‌کند."""
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import PeriodStatus
from app.models.evaluation import EvaluationRecord
from app.models.evaluation_period import EvaluationPeriod


def period_accepts_entries(period: EvaluationPeriod, *, today: date | None = None) -> bool:
    current = today or date.today()
    return (
        period.status == PeriodStatus.open
        and period.starts_on <= current <= period.ends_on
    )


def open_period(db: Session) -> EvaluationPeriod | None:
    return db.scalar(
        select(EvaluationPeriod).where(EvaluationPeriod.status == PeriodStatus.open)
    )


def require_active_period(db: Session) -> EvaluationPeriod:
    """دوره‌ای که همین امروز اجازهٔ ساخت یا ثبت ارزیابی می‌دهد."""
    period = open_period(db)
    if period is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="هیچ دورهٔ ارزیابی بازی وجود ندارد؛ منابع انسانی باید ابتدا دوره را تعریف کند",
        )
    current = date.today()
    if current < period.starts_on:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="بازهٔ ثبت این دوره هنوز آغاز نشده است",
        )
    if current > period.ends_on:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "مهلت ثبت این دوره پایان یافته است؛ منابع انسانی می‌تواند تاریخ پایان "
                "دوره را تمدید کند"
            ),
        )
    return period


def record_accepts_entries(db: Session, record: EvaluationRecord) -> bool:
    if record.period_id is None:
        return False
    period = db.get(EvaluationPeriod, record.period_id)
    return period is not None and period_accepts_entries(period)


def require_record_window(db: Session, record: EvaluationRecord) -> EvaluationPeriod:
    """ثبت روی پرونده را فقط در بازهٔ دورهٔ خودش مجاز کند."""
    if record.period_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این پرونده به دورهٔ ارزیابی متصل نیست؛ منابع انسانی باید آن را تعیین تکلیف کند",
        )
    period = db.get(EvaluationPeriod, record.period_id)
    if period is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دورهٔ مرتبط با این پرونده یافت نشد",
        )
    if period.status != PeriodStatus.open:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این دوره بسته شده و امکان ثبت ارزیابی وجود ندارد",
        )
    current = date.today()
    if current < period.starts_on:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="بازهٔ ثبت این دوره هنوز آغاز نشده است",
        )
    if current > period.ends_on:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "مهلت ثبت این دوره پایان یافته است؛ منابع انسانی می‌تواند تاریخ پایان "
                "دوره را تمدید کند"
            ),
        )
    return period
