"""نسخهٔ چارچوب شاخص‌ها (P1-05).

`ScoringScheme` جواب داد که «با چه قاعده‌ای حساب می‌شود». این‌جا جواب سؤال قبلی
است: «اصلاً چه چیزهایی پرسیده شد».

تا امروز جواب همیشه «هرچه *الان* فعال است» بود، و همین دو خرابیِ بی‌صدا می‌ساخت:

۱. ارزیاب فرم را کامل پر می‌کرد و می‌رفت؛ منابع انسانی سؤالی اضافه یا کم می‌کرد؛
   فردا «ثبت» کار نمی‌کرد و پیام می‌گفت «به تمام شاخص‌ها امتیاز بدهید» — برای
   سؤالی که آن روز اصلاً وجود نداشت. هیچ‌کس هم به HR نگفته بود که با یک ویرایش،
   دوازده پروندهٔ در جریان را قفل کرده است.
۲. متن شاخص درجا قابل بازنویسی بود. نموداری که «شاخص ۷» را در دو سال کنار هم
   می‌گذارد، ممکن بود دو سؤالِ متفاوت را مقایسه کند و نمودار هیچ نشانه‌ای از این
   نداشته باشد.

قاعدهٔ این ماژول، همان قاعدهٔ P1-04 است یک قدم عقب‌تر:

    هر پرونده به نسخهٔ چارچوبی که *زیر آن باز شده* مهر می‌خورد، و «کامل بودن»
    همیشه با همان نسخه سنجیده می‌شود — نه با مجموعهٔ فعالِ امروز.

یک تفاوت عمدی با طرح نمره‌دهی: نسخهٔ چارچوب **فعال‌سازی دستی ندارد**. اضافه‌کردن
یک سؤال کارِ روزمرهٔ منابع انسانی است، نه تصمیمی که دو نفر باید امضایش کنند؛ پس
نسخه به‌عنوان *نتیجهٔ* ویرایش ساخته می‌شود نه به‌عنوان کاری جدا. گردش کار HR
دست‌نخورده می‌ماند و پایداری تاریخ رایگان به‌دست می‌آید.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IndicatorFramework(Base):
    """عضویتِ مجموعهٔ شاخص‌ها در یک لحظه از زمان."""

    __tablename__ = "indicator_frameworks"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: شمارهٔ نسخه — یکتا و صعودی. چیزی است که در گزارش‌ها به کاربر نشان داده می‌شود.
    version: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)

    #: شناسهٔ شاخص‌های عضو این نسخه، مرتب. عمداً *فقط شناسه* و نه متن: متنِ یک
    #: شاخصِ استفاده‌شده دیگر قابل تغییرِ معنایی نیست (اصلاح نگارشی جدا حساب
    #: می‌شود)، پس نگه‌داشتن دوبارهٔ متن یعنی دو منبع حقیقت که دیر یا زود واگرا
    #: می‌شوند. سندِ نهایی هم متن را جداگانه در `final_snapshot` نگه می‌دارد.
    member_ids: Mapped[list] = mapped_column(JSONB, nullable=False)

    #: چه چیزی این نسخه را ساخت — برای اینکه تاریخچه خوانا باشد، نه فقط موجود.
    change_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    #: توضیح انسانی، جایی که تغییر معنادار است (جایگزینی یک شاخص، یا اصلاح متن).
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
