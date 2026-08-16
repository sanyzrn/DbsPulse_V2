"""ماژول‌های قابل روشن/خاموش کردن (نیمهٔ دوم P0-03).

`FEATURE_PERIODS_ENABLED` یک ثابت در کد فرانت‌اند بود: روشن‌کردنش یعنی تغییر کد،
بیلد و استقرار. برای محصولی که قرار است به چند سازمان فروخته شود، این یعنی هر
تفاوتِ «این بخش را نمی‌خواهیم» یک انشعاب است.

همان کاری که P1-04 با وزن‌های نمره‌دهی کرد، این‌جا با خودِ بخش‌ها انجام می‌شود.

**خاموش‌کردن هیچ داده‌ای را حذف نمی‌کند.** فقط ورودی‌های نوشتن بسته و بخش از
منو برداشته می‌شود؛ آنچه قبلاً ثبت شده سر جایش می‌ماند و با روشن‌کردن دوباره
برمی‌گردد. یک سوییچ که داده پاک کند، سوییچ نیست — یک تلهٔ کلیکِ اشتباه است.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModuleSetting(Base):
    __tablename__ = "module_settings"

    #: کلید ماژول، از app/core/modules.py — همان‌جا فهرست معتبرها تعریف شده
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
