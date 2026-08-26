"""دستیار هوشمند: تنظیمات سراسری، دسترسی هر کاربر، و تاریخچهٔ گفت‌وگو.

چرا تنظیمات در دیتابیس است و نه در `.env`
------------------------------------------
بقیهٔ تنظیماتِ سرویس‌های بیرونی (SMTP، پیامک) یک نسخه دارند و برای کل سازمان
یکی‌اند. این یکی نیست: مدیر می‌خواهد بگوید «معاونت دستیار داشته باشد، مسئول
واحد نه»، و برای هر کدام کلید جداگانه بگذارد تا هزینه و سهمیه از هم جدا بماند.
چنین چیزی در فایل تنظیمات جا نمی‌شود.

چرا کلیدها رمزنگاری‌شده ذخیره می‌شوند
--------------------------------------
همان قاعده‌ای که رمز SMTP را از دیتابیس بیرون نگه داشت این‌جا قابل اجرا نیست —
کلید *باید* در دیتابیس باشد چون به کاربر گره خورده. پس به‌جای بیرون نگه‌داشتن،
رمز می‌شود: کلیدِ رمزنگاری از `.env` می‌آید، یعنی یک بک‌آپِ دیتابیسِ لو رفته به
تنهایی هیچ کلید API معتبری نمی‌دهد. API هم هرگز مقدار را برنمی‌گرداند، فقط
«تنظیم شده یا نه» و چهار نویسهٔ آخر.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: متنِ پیش‌فرضِ «چطور جواب بده». مدیر می‌تواند کاملاً عوضش کند.
DEFAULT_INSTRUCTIONS = (
    "تو دستیار سامانهٔ ارزیابی عملکرد سازمانی «DbsPulse» هستی. "
    "کوتاه، دقیق و به فارسی جواب می‌دهی. "
    "وقتی عددی می‌گویی، منبعش را از داده‌های همین سامانه بگیر و اگر داده‌ای نداری، "
    "صریح بگو که نمی‌دانی — حدس نزن."
)


class AiSettings(Base):
    """تنظیمات سراسری — همیشه یک ردیف با `id = 1`.

    جدولِ تک‌ردیفی و نه کلید/مقدار: این‌ها یک *پیکربندی* هستند نه مجموعه‌ای از
    پرچم‌های مستقل، و با ستون، تایپ و مقدار پیش‌فرضِ هرکدام در خودِ schema
    می‌نشیند به‌جای اینکه در کدِ خواننده تکرار شود.
    """

    __tablename__ = "ai_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)

    #: کلید اصلی: خاموش که باشد، هیچ کاربری دستیار نمی‌بیند، حتی اگر دسترسی
    #: فردی‌اش روشن باشد.
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    #: کدام سرویسِ آماده انتخاب شده. «custom» یعنی آدرس دستی.
    provider: Mapped[str] = mapped_column(String(40), default="custom", nullable=False)

    #: نقطهٔ پایانیِ سازگار با OpenAI. خالی یعنی «تنظیم نشده».
    base_url: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    model: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    #: کلید پیش‌فرض، برای کاربرانی که کلید اختصاصی ندارند. رمزنگاری‌شده.
    api_key_encrypted: Mapped[str] = mapped_column(Text, default="", nullable=False)

    temperature: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1200, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    #: «چطور جواب بده» — متنی که سرِ هر گفت‌وگو به مدل داده می‌شود.
    instructions: Mapped[str] = mapped_column(Text, default=DEFAULT_INSTRUCTIONS, nullable=False)

    #: بیرون از موضوعِ سامانه جواب بدهد یا نه. پیش‌فرض «نه»: مدلِ ارزان در یک
    #: سامانهٔ ارزیابی، هم بی‌ربط جواب می‌دهد و هم بد.
    restrict_to_platform: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    #: چند ردیف داده همراه هر پرسش برای مدل فرستاده شود. صفر یعنی هیچ.
    context_record_limit: Mapped[int] = mapped_column(Integer, default=25, nullable=False)

    #: اجازهٔ *پیشنهادِ* تغییر. حتی وقتی روشن است، هیچ تغییری بدون تأیید کاربر
    #: اجرا نمی‌شود؛ خاموش‌بودنش یعنی دستیار فقط می‌خواند.
    allow_write_actions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    #: سقفِ پیامِ کاربر. بدون آن، یک paste بلند هم هزینه است و هم احتمال خطای سرویس.
    max_user_chars: Mapped[int] = mapped_column(Integer, default=4000, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AiUserAccess(Base):
    """دسترسیِ یک کاربر مشخص به دستیار.

    نبودِ ردیف = دسترسی ندارد. یعنی حالت پیش‌فرضِ هر حساب تازه «بدون دستیار»
    است و روشن‌کردنش یک کارِ صریح است، نه چیزی که با ساختِ حساب اتفاق بیفتد.
    """

    __tablename__ = "ai_user_access"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    #: کلید اختصاصیِ همین کاربر. خالی یعنی از کلید سراسری استفاده می‌کند.
    api_key_encrypted: Mapped[str] = mapped_column(Text, default="", nullable=False)
    #: مدلِ اختصاصی. خالی یعنی همان مدل سراسری.
    model: Mapped[str] = mapped_column(String(120), default="", nullable=False)

    #: آیا این کاربر می‌تواند تغییر *پیشنهاد* بگیرد. برای حسابی مثل معاونت که
    #: فقط باید بپرسد، خاموش می‌ماند.
    allow_write_actions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    #: سقف پیام در روز. صفر یعنی بی‌حد.
    daily_message_limit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiConversation(Base):
    __tablename__ = "ai_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AiMessage(Base):
    __tablename__ = "ai_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: "user" | "assistant"
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    #: پیشنهادهای تغییر، به‌صورت JSON. تا وقتی کاربر تأیید نکرده، فقط متن‌اند.
    actions_json: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
