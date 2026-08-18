"""مقدارهای تنظیماتِ ارسال بیرونی که از پنل عوض می‌شوند.

هم‌الگوی `ModuleSetting`: کلید از `app/core/integrations.py` می‌آید و کد منبعِ
حقیقتِ «چه تنظیماتی وجود دارند» است؛ این جدول فقط می‌گوید هرکدام چه مقداری
گرفته‌اند.

**رمز و کلید API این‌جا نمی‌آیند.** چیزی که در دیتابیس بنشیند، در هر بک‌آپی هم
می‌نشیند — و بک‌آپ دیتابیس معمولاً جاهایی می‌رود که فایل `.env` نمی‌رود. آن‌ها
در `.env` می‌مانند و پنل فقط می‌گوید تنظیم شده‌اند یا نه.

مقدار به‌صورت متن ذخیره می‌شود چون همین حالا سه نوع دارد (متن، عدد، بولی) و
ستونِ نوع‌دار برای هرکدام یعنی سه ستونِ عمدتاً خالی. تبدیل در لحظهٔ خواندن انجام
می‌شود، جایی که نوعِ درست از روی همان تعریفِ کد معلوم است.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IntegrationSetting(Base):
    __tablename__ = "integration_settings"

    #: نامش دقیقاً همان صفتِ `Settings` است — نگاشت دوم یعنی جایی از هم دور می‌افتند.
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
