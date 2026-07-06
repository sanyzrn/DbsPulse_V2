from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
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
