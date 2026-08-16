"""مجوزهای اداری، مستقل از نقش (نیمهٔ دوم P0-03).

تا امروز `hr` هم‌زمان کاربر عادی و مدیر سامانه بود: همان کسی که پرونده‌ها را
تأیید می‌کند، کاربر می‌سازد، شاخص‌ها را عوض می‌کند و قواعد نمره‌دهی را فعال
می‌کند. اگر روزی نتیجه‌ای زیر سؤال برود، نمی‌شود ثابت کرد کسی که تصمیم گرفته
همان کسی نبوده که قاعده را نوشته.

**چرا مجوز، و نه یک نقش تازه؟** نقش‌های موجود جایگاه‌های *زنجیرهٔ ارزیابی*‌اند —
مسئول واحد، معاونت، مدیرعامل. «مدیر سامانه» در آن زنجیره جایی ندارد. اگر
به‌صورت یک نقشِ همه‌کاره اضافه می‌شد، همان مشکل `hr` را با نامی تازه تکرار
می‌کرد.

پس دو چیز جدا شد:

* **نقش** می‌گوید در زنجیرهٔ ارزیابی کجایی. نقش `support` عمداً *هیچ* جایی در
  آن ندارد و در هیچ گاردِ گردش‌کاری فهرست نشده — یعنی به‌صورت پیش‌فرض روی همهٔ
  آن‌ها ۴۰۳ می‌گیرد. کسی که سامانه را نگه می‌دارد، لازم نیست نمرهٔ کسی را ببیند.
* **مجوز** می‌گوید چه کار اداری‌ای می‌توانی بکنی. به هر کاربری قابل دادن است،
  از جمله `hr` — پس سازمانی که یک نفر بیشتر ندارد می‌تواند همه را به او بدهد،
  و سازمانی که می‌خواهد تفکیک کند، از HR می‌گیرد و به حساب پشتیبانی می‌دهد.

هر اعطا ثبت می‌کند چه کسی و کِی — همان چیزی که کل این کار برایش انجام شده.
"""
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import Capability


class UserCapability(Base):
    __tablename__ = "user_capabilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    capability: Mapped[Capability] = mapped_column(
        Enum(Capability, name="capability", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    #: چه کسی این مجوز را داد. null یعنی مایگریشن (حساب‌های موجود هنگام ارتقا).
    granted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # یک مجوز، یک بار. بدون این، «گرفتنِ» مجوز باید همهٔ ردیف‌های تکراری را
        # پیدا می‌کرد و اولین ردیفِ جامانده یعنی مجوز هرگز واقعاً گرفته نشده.
        UniqueConstraint("user_id", "capability", name="uq_user_capability"),
        Index("ix_user_capabilities_user", "user_id"),
    )
