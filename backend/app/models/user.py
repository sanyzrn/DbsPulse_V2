from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    personnel_id: Mapped[int | None] = mapped_column(
        ForeignKey("personnel.id", use_alter=True, name="fk_users_personnel_id"),
        nullable=True,
    )
    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    # نام قابل‌نمایشِ صاحب حساب. خالی‌پذیر، و عمداً جدا از `personnel.full_name`:
    # حساب‌های نقش‌دار (معاونت، مدیرعامل، مسئول واحد، منابع انسانی) پروندهٔ پرسنلی
    # ندارند، پس تا امروز همه‌جا با نام کاربری دیده می‌شدند — «dep1» به‌جای
    # «معاونت، آقای رضایی». آن نام کاربری برای *ورود* است، نه برای شناساندنِ
    # کسی که پای یک ارزیابی امضا گذاشته.
    #
    # اگر حساب به پرسنل وصل باشد، منبع نام همان پرونده است و این ستون لازم نیست؛
    # `display_name` همین ترتیب را پیاده می‌کند.
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # --- تماس و ارجحیت اعلان (P1-03) --------------------------------------
    # هر دو خالی‌پذیرند: سامانه بدون هیچ نشانی تماسی هم کاملاً کار می‌کند و فقط
    # اعلان درون‌برنامه‌ای می‌دهد — همان رفتار امروز.
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # پیش‌فرض هر دو خاموش است، و این عمدی است: اولین باری که کانالی روشن شود،
    # نباید کل سازمان بی‌خبر پیام بگیرد. هرکس خودش انتخاب می‌کند.
    notify_by_email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_by_sms: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ایندکس‌ها در مایگریشن‌ها ساخته شده‌اند و تا امروز روی مدل اعلام نشده بودند،
    # پس `alembic revision --autogenerate` آن‌ها را «اضافی» می‌دید و DROP پیشنهاد
    # می‌داد. اعلامشان این‌جا یعنی autogenerate واقعیتِ دیتابیس را می‌بیند.
    __table_args__ = (
        Index("ix_users_is_active", "is_active"),
    )

    @property
    def display_name(self) -> str:
        """نامی که باید به آدم‌ها نشان داده شود، و هیچ‌وقت خالی نیست.

        نام کاربری آخرین گزینه است، نه گزینهٔ اول: تا وقتی نامی ثبت نشده باشد
        صفحه نباید خالی بماند. جایی که حساب به پرسنل وصل است، لایهٔ API نام
        پرونده را ترجیح می‌دهد — آن نام را همان‌جا از قبل خوانده و اضافه‌کردن
        یک relationship این‌جا فقط یک کوئری اضافه به‌ازای هر ردیف می‌شد.
        """
        return self.full_name or self.username
