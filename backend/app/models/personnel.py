from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import PersonnelStatus, SeparationReason


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
    # --- خروج از سازمان -----------------------------------------------------
    # هر دو خالی‌پذیرند و فقط برای پرسنلِ غیرفعال معنا دارند. جدا از
    # `contract_end_date` نگه داشته شده‌اند و این عمدی است: تاریخ پایان قرارداد
    # یک *برنامه* است که ممکن است هرگز اتفاق نیفتد (تمدید می‌شود)، و تاریخ خروج
    # یک *واقعه* است. یکی‌کردنشان یعنی نشود گفت چند نفر پیش از پایان قراردادشان
    # رفتند — که دقیقاً همان چیزی است که باید دیده شود.
    separation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    separation_reason: Mapped[SeparationReason | None] = mapped_column(
        Enum(
            SeparationReason,
            name="separation_reason",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )

    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ایندکس‌ها در مایگریشن‌ها ساخته شده‌اند و تا امروز روی مدل اعلام نشده بودند،
    # پس `alembic revision --autogenerate` آن‌ها را «اضافی» می‌دید و DROP پیشنهاد
    # می‌داد. اعلامشان این‌جا یعنی autogenerate واقعیتِ دیتابیس را می‌بیند.
    __table_args__ = (
        Index("ix_personnel_org_unit", "org_unit"),
        Index("ix_personnel_status", "status"),
    )
