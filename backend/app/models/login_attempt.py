from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LoginAttempt(Base):
    """شمارش تلاش‌های ناموفق ورود، به ازای «نام کاربری» — نه IP.

    محدودیت نرخِ per-IP یک حملهٔ توزیع‌شده و آهسته روی یک حساب مشخص را نمی‌گیرد:
    مهاجم فقط کافی است از چند IP یا با فاصلهٔ زمانی بیشتر تلاش کند. هش Argon2 از
    خودِ رمز محافظت می‌کند، ولی از *حساب* محافظت نمی‌کند.

    عمداً در Postgres است نه حافظهٔ پروسه: با چند replica مشترک می‌ماند و با ری‌استارت
    پاک نمی‌شود — دقیقاً دو ضعفی که شمارندهٔ درون‌پروسه دارد.

    نام‌های کاربری ناموجود هم شمرده می‌شوند؛ اگر فقط حساب‌های واقعی قفل می‌شدند،
    خودِ رفتار قفل به یک اوراکل «این نام کاربری وجود دارد» تبدیل می‌شد.
    """

    __tablename__ = "login_attempts"

    username: Mapped[str] = mapped_column(String(150), primary_key=True)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # تا این لحظه ورود پذیرفته نمی‌شود، حتی با رمز درست
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
