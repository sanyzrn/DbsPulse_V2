from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.text_limits import SELF_ASSESSMENT_NOTE_MAX
from app.db.base import Base


class SelfAssessmentScore(Base):
    """امتیازی که خودِ کارمند به یک شاخص داده است.

    عمداً جدولی جدا از evaluation_scores است، نه یک ستون کنار آن. محاسبهٔ نتیجه
    (finalize_scoring) فقط از evaluation_scores می‌خواند، پس این ساختار *به‌طور
    ساختاری* تضمین می‌کند نظر کارمند هرگز وارد میانگین نمی‌شود — نه به این دلیل که
    یک شرط جایی یادش نرفته باشد.

    این یک دیدگاه دوم است، نه یک رأی: کنار امتیاز ارزیاب نمایش داده می‌شود تا فاصله‌ها
    دیده و دربارهٔ آن‌ها گفت‌وگو شود.
    """

    __tablename__ = "self_assessment_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_record_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_records.id"), nullable=False
    )
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicators.id"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    # دستاورد/توضیح خود فرد دربارهٔ همین شاخص
    note: Mapped[str | None] = mapped_column(String(SELF_ASSESSMENT_NOTE_MAX), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("score BETWEEN 1 AND 5", name="ck_self_assessment_scores_score_range"),
        Index("ix_self_assessment_scores_record", "evaluation_record_id"),
        UniqueConstraint(
            "evaluation_record_id", "indicator_id", name="uq_self_assessment_record_indicator"
        ),
    )
