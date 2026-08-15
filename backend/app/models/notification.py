from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Notification(Base):
    """اعلان درون‌برنامه‌ای برای یک کاربر مشخص (زنگوله بالای صفحه).

    سیستم تا الان کاملاً pull-based بود: تأییدکننده باید یادش می‌ماند وارد شود.
    اعلان‌ها در همان تراکنشِ رویداد ساخته می‌شوند تا با خود رویداد atomic باشند.
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # مسیر داخلی SPA برای کلیک روی اعلان، مثلاً /evaluations/7
    link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    evaluation_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("evaluation_records.id"), nullable=True
    )
    # کلید یکتاسازی برای اعلان‌های زمان‌بندی‌شده؛ تا همان هشدار در هر اجرای sweep تکرار نشود
    dedup_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ایندکس‌ها در مایگریشن‌ها ساخته شده‌اند و تا امروز روی مدل اعلام نشده بودند،
    # پس `alembic revision --autogenerate` آن‌ها را «اضافی» می‌دید و DROP پیشنهاد
    # می‌داد. اعلامشان این‌جا یعنی autogenerate واقعیتِ دیتابیس را می‌بیند.
    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "read_at"),
        Index("ix_notifications_created_at", "created_at"),
        Index("ix_notifications_dedup", "user_id", "dedup_key", "created_at"),
    )
