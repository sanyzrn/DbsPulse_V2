from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.text_limits import PLAN_GOAL_MAX, PLAN_SUMMARY_MAX
from app.db.base import Base
from app.models.enums import ImprovementPlanStatus
from app.models.personnel import Personnel  # noqa: TC001  (relationship target)


class ImprovementPlan(Base):
    """برنامه بهبود مکتوب (R13.2): وقتی نتیجه ارزیابی «تمدید مشروط به برنامه بهبود
    مکتوب» است، منابع انسانی این برنامه را با اهداف مشخص، مسئول پیگیری و تاریخ
    بازنگری مدیریت می‌کند — تا سامانه سندی را که خودش تجویز می‌کند، رها نکند."""

    __tablename__ = "improvement_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    # هر ارزیابی حداکثر یک برنامه بهبود دارد (ایندکس یکتا)
    evaluation_record_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_records.id"), unique=True, nullable=False
    )
    # از موضوع ارزیابی مشتق می‌شود؛ برای فهرست‌ها و پیوند ارزیابی پیگیری نگه داشته می‌شود
    personnel_id: Mapped[int] = mapped_column(ForeignKey("personnel.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # مسئول پیگیری برنامه (معمولاً مسئول واحد یا معاونت)؛ اختیاری
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[ImprovementPlanStatus] = mapped_column(
        Enum(
            ImprovementPlanStatus,
            name="improvement_plan_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ImprovementPlanStatus.open,
        nullable=False,
    )
    review_date: Mapped[date] = mapped_column(Date, nullable=False)
    summary: Mapped[str | None] = mapped_column(String(PLAN_SUMMARY_MAX), nullable=True)
    # ارزیابی پیگیری که بعداً برای سنجش نتیجه برنامه انجام می‌شود؛ تا آن زمان NULL
    follow_up_evaluation_id: Mapped[int | None] = mapped_column(
        ForeignKey("evaluation_records.id"), nullable=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    goals: Mapped[list["ImprovementPlanGoal"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="ImprovementPlanGoal.display_order",
    )
    # eager join تا فهرست‌ها بدون N+1 نام پرسنل را همراه داشته باشند
    personnel: Mapped["Personnel"] = relationship(lazy="joined")

    @property
    def personnel_full_name(self) -> str:
        return self.personnel.full_name


class ImprovementPlanGoal(Base):
    __tablename__ = "improvement_plan_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("improvement_plans.id"), nullable=False)
    description: Mapped[str] = mapped_column(String(PLAN_GOAL_MAX), nullable=False)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    plan: Mapped["ImprovementPlan"] = relationship(back_populates="goals")
