from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import PersonnelStatus


class Personnel(Base):
    __tablename__ = "personnel"

    id: Mapped[int] = mapped_column(primary_key=True)
    personnel_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    job_title: Mapped[str] = mapped_column(String(150), nullable=False)
    # مسیر ارزیابی «مدیر» (نمره‌دهی مستقیم توسط معاونت) با این پرچم صریح تعیین می‌شود،
    # نه با مقایسه متن آزاد عنوان شغلی با رشته جادویی «مدیر».
    is_manager: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    org_unit: Mapped[str] = mapped_column(String(150), nullable=False)
    contract_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PersonnelStatus] = mapped_column(
        Enum(PersonnelStatus, name="personnel_status", values_callable=lambda e: [m.value for m in e]),
        default=PersonnelStatus.active,
        nullable=False,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
