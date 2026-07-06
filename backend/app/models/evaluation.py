from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import CommentStage, EvaluationStatus
from app.models.personnel import Personnel  # noqa: TC001  (relationship target)
from app.models.user import User  # noqa: TC001  (relationship target)


class EvaluationRecord(Base):
    __tablename__ = "evaluation_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    subject_personnel_id: Mapped[int] = mapped_column(ForeignKey("personnel.id"), nullable=False)
    unit_supervisor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deputy_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    ceo_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # دوره‌ای که این ارزیابی در آن انجام شده؛ ارزیابی‌های خارج از دوره NULL می‌مانند
    period_id: Mapped[int | None] = mapped_column(ForeignKey("evaluation_periods.id"), nullable=True)
    # ستون stage حذف شد: همیشه ۱:۱ از status قابل استخراج بود و دو منبع حقیقت
    # هم‌معنا خطر واگرایی داشت. مقدار stage در API از status مشتق می‌شود
    # (app/schemas/evaluation.py).
    status: Mapped[EvaluationStatus] = mapped_column(
        Enum(EvaluationStatus, name="evaluation_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    general_score_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    specialized_score_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    final_weighted_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluator_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # رؤیت رسمی نتیجه توسط خود کارمند (نقش employee) پس از نهایی شدن
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    scores: Mapped[list["EvaluationScore"]] = relationship(
        back_populates="evaluation_record", cascade="all, delete-orphan"
    )
    comments: Mapped[list["EvaluationComment"]] = relationship(
        back_populates="evaluation_record", cascade="all, delete-orphan"
    )
    # eager join تا فهرست‌ها بدون N+1 نام پرسنل را همراه داشته باشند
    subject: Mapped["Personnel"] = relationship(lazy="joined")

    @property
    def subject_full_name(self) -> str:
        return self.subject.full_name


class EvaluationScore(Base):
    __tablename__ = "evaluation_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_record_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_records.id"), nullable=False
    )
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicators.id"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    evaluation_record: Mapped["EvaluationRecord"] = relationship(back_populates="scores")

    __table_args__ = (CheckConstraint("score BETWEEN 1 AND 5", name="ck_evaluation_scores_score_range"),)


class EvaluationComment(Base):
    __tablename__ = "evaluation_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_record_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_records.id"), nullable=False
    )
    commenter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    stage: Mapped[CommentStage] = mapped_column(
        Enum(CommentStage, name="comment_stage", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    evaluation_record: Mapped["EvaluationRecord"] = relationship(back_populates="comments")
    commenter: Mapped["User"] = relationship(lazy="joined")

    @property
    def commenter_username(self) -> str | None:
        return self.commenter.username if self.commenter else None
