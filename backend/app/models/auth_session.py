from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuthSession(Base):
    """یک refresh token صادرشده = یک ردیف نشست؛ برای ابطال سمت سرور (خروج، سرقت توکن)
    و چرخش (rotation) توکن‌ها. توکن دسترسی همچنان stateless است و با token_version
    کاربر باطل می‌شود."""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # چرخش: توکن قدیمی جای خود را به توکن جدید می‌دهد؛ استفاده دوباره از توکنِ
    # چرخیده بعد از مهلت کوتاه = نشانه سرقت → همه نشست‌های کاربر باطل می‌شوند.
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_jti: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── شناسایی نشست برای خودِ کاربر (P2-06)
    #
    # «شما سه نشست فعال دارید» بی‌فایده است اگر کاربر نتواند بگوید کدام‌یک خودش
    # است. این سه ستون فقط برای همین‌اند: تشخیص «این لپ‌تاپ خودم است» از «این را
    # نمی‌شناسم». عمداً user-agent خام ذخیره می‌شود نه تحلیل‌شده — تحلیلش کارِ
    # نمایش است و رشتهٔ خام بعداً هم قابل بازخوانی است.
    user_agent: Mapped[str | None] = mapped_column(String(400), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)  # جا برای IPv6
    # با هر چرخش به‌روز می‌شود؛ «آخرین فعالیت» چیزی است که کاربر با آن نشستِ
    # فراموش‌شده را از نشست جاری تشخیص می‌دهد.
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ایندکس‌ها در مایگریشن‌ها ساخته شده‌اند و تا امروز روی مدل اعلام نشده بودند،
    # پس `alembic revision --autogenerate` آن‌ها را «اضافی» می‌دید و DROP پیشنهاد
    # می‌داد. اعلامشان این‌جا یعنی autogenerate واقعیتِ دیتابیس را می‌بیند.
    __table_args__ = (
        Index("ix_auth_sessions_user", "user_id"),
    )
