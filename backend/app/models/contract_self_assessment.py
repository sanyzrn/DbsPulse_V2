from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.text_limits import SELF_ASSESSMENT_NOTE_MAX, SELF_ASSESSMENT_SUMMARY_MAX
from app.db.base import Base


class ContractSelfAssessment(Base):
    """A personnel-owned self-assessment, submitted once per employment contract."""

    __tablename__ = "contract_self_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    personnel_id: Mapped[int] = mapped_column(ForeignKey("personnel.id"), nullable=False)
    contract_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    indicator_framework_id: Mapped[int] = mapped_column(ForeignKey("indicator_frameworks.id"), nullable=False)
    submitted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    source_evaluation_record_id: Mapped[int | None] = mapped_column(ForeignKey("evaluation_records.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(SELF_ASSESSMENT_SUMMARY_MAX))
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invited_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    personnel = relationship("Personnel", lazy="joined")
    scores: Mapped[list["ContractSelfAssessmentScore"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint(
            "personnel_id",
            "contract_start_date",
            name="uq_contract_self_assessment_personnel_contract",
        ),
        UniqueConstraint(
            "source_evaluation_record_id",
            name="uq_contract_self_assessment_source_evaluation",
        ),
        Index("ix_contract_self_assessments_personnel", "personnel_id"),
    )


class ContractSelfAssessmentScore(Base):
    __tablename__ = "contract_self_assessment_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_self_assessment_id: Mapped[int] = mapped_column(
        ForeignKey("contract_self_assessments.id", ondelete="CASCADE"), nullable=False
    )
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicators.id"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(String(SELF_ASSESSMENT_NOTE_MAX))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    assessment: Mapped[ContractSelfAssessment] = relationship(back_populates="scores")

    __table_args__ = (
        CheckConstraint(
            "score BETWEEN 1 AND 5",
            name="ck_contract_self_assessment_scores_range",
        ),
        UniqueConstraint(
            "contract_self_assessment_id",
            "indicator_id",
            name="uq_contract_self_assessment_score_indicator",
        ),
        Index(
            "ix_contract_self_assessment_scores_assessment",
            "contract_self_assessment_id",
        ),
    )
