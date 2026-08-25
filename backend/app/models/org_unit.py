"""فهرست واحدهای سازمانی — یک *کاتالوگ*، نه یک کلید خارجی.

چرا کاتالوگ و نه رابطه
----------------------
`personnel.org_unit` یک رشتهٔ آزاد است و در حدود صد نقطه از کد خوانده می‌شود:
فیلترها، گزارش‌ها، خروجی اکسل، PDF کارنامه، تجمیع‌های داشبورد. تبدیلش به کلید
خارجی یعنی هر کدام از آن صد نقطه یک فرصت برای شکستن چیزی که امروز کار می‌کند —
و هیچ‌کدام از آن‌ها از این تغییر چیزی به دست نمی‌آورند.

آنچه واقعاً کم بود این نبود که واحد یک ردیف در جدول باشد؛ این بود که کسی نمی‌
توانست *فهرست* واحدها را تعریف کند. تا امروز فهرست از روی خودِ داده ساخته
می‌شد: هر واحدی که کسی در آن ثبت شده بود. یعنی یک غلط تایپی («فناوری اطلاعا»)
بی‌سروصدا یک واحد تازه می‌ساخت، و واحدی که هنوز کسی در آن نبود اصلاً وجود
نداشت.

پس این جدول فقط فهرست را نگه می‌دارد. `personnel.org_unit` همان رشته می‌ماند و
هیچ کوئری موجودی دست نمی‌خورد. اگر روزی رابطهٔ واقعی لازم شد، این جدول همان
جایی است که از آن شروع می‌شود.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrgUnit(Base):
    __tablename__ = "org_units"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: محل (دفتر مرکزی / کارخانه / مدرپ‌ها). خالی یعنی واحدی که به محل خاصی
    #: وابسته نیست — سازمانی که یک محل بیشتر ندارد همهٔ واحدهایش این‌طورند.
    site: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    #: غیرفعال یعنی «دیگر برای ثبتِ تازه پیشنهاد نشو» — نه «حذف شو». پرسنلی که
    #: از قبل در این واحد است سر جایش می‌ماند و گزارش‌های گذشته نمی‌شکنند.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("site", "name", name="uq_org_unit_site_name"),)

    @property
    def full_name(self) -> str:
        """همان رشته‌ای که در `personnel.org_unit` می‌نشیند."""
        from app.services.org_unit import join_site

        return join_site(self.site, self.name)
