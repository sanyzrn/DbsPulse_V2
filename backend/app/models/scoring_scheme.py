"""طرح نمره‌دهی، نسخه‌دار (P1-04).

تا امروز وزن بخش‌ها، قاعدهٔ شواهد و جدول آستانه‌ها ثابت‌های پایتون بودند. یعنی
مشتری‌ای که ۷۰/۳۰ می‌خواست، یا یک بازهٔ پنجم، یا شواهد اجباری روی نمرهٔ ۲، به یک
تغییر کد و بیلد و استقرار نیاز داشت — و عملاً این محصول به سازمان دوم فروختنی
نبود مگر با انشعاب رفتار.

ولی «قابل ویرایش کردنشان» به‌تنهایی راه‌حل نیست؛ بدتر است. اگر HR وزن‌ها را عوض
کند و محاسبه همیشه از *آخرین* تنظیمات بخواند، معنای هر ارزیابی گذشته بی‌صدا
بازنویسی می‌شود: پرونده‌ای که پارسال «تمدید با شرایط استاندارد» گرفته، امروز
ممکن است «عدم تمدید» نشان بدهد، بدون اینکه هیچ نمره‌ای عوض شده باشد. در سامانه‌ای
که خروجی‌اش تصمیم تمدید قرارداد است، این یک فاجعهٔ سکوت است.

پس قاعدهٔ اصلی این ماژول:

    هر پرونده به نسخهٔ طرحی که *زیر آن ساخته شده* مهر می‌خورد، و محاسبه همیشه
    از همان نسخه می‌خواند — نه از نسخهٔ فعال.

با این کار پایداری تاریخ یک خاصیت ساختاری می‌شود، نه چیزی که باید به یاد داشت.

نسخهٔ فعال‌شده **تغییرناپذیر** است: برای عوض کردن هر عددی باید نسخهٔ تازه‌ای
ساخته و فعال شود. ویرایش درجای یک نسخهٔ فعال دقیقاً همان بازنویسی تاریخ است که
این طراحی برای جلوگیری از آن ساخته شده.
"""
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import SchemeStatus


class ScoringScheme(Base):
    """یک نسخه از قواعد نمره‌دهی."""

    __tablename__ = "scoring_schemes"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: شمارهٔ نسخه — یکتا و تغییرناپذیر. چیزی است که در پرونده مهر می‌شود.
    version: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    status: Mapped[SchemeStatus] = mapped_column(
        Enum(SchemeStatus, name="scheme_status", values_callable=lambda e: [m.value for m in e]),
        default=SchemeStatus.draft,
        nullable=False,
    )

    # --- وزن بخش‌ها ---------------------------------------------------------
    # Numeric نه float: این اعداد در محاسبهٔ نتیجهٔ یک تصمیم رسمی وارد می‌شوند و
    # خطای ممیز شناور در جمعِ ۰٫۷+۰٫۳ چیزی است که نباید در سند حقوقی دیده شود.
    general_section_weight: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    specialized_section_weight: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)

    # --- قاعدهٔ شواهد -------------------------------------------------------
    #: کدام امتیازها شواهد اجباری دارند، مثلاً [1, 5]
    evidence_required_scores: Mapped[list] = mapped_column(JSONB, nullable=False)
    evidence_min_words: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_max_words: Mapped[int] = mapped_column(Integer, nullable=False)

    #: جدول آستانه‌ها: [{"upper_exclusive": 60, "label": "..."}, ...]
    #: بازه‌ها نیم‌باز و پیوسته‌اند تا کل [0, 100] بدون شکاف پوشش داده شود.
    thresholds: Mapped[list] = mapped_column(JSONB, nullable=False)

    #: وزن هر شاخص: {"<indicator_id>": 1.5, ...}. شاخصی که این‌جا نیست وزن ۱
    #: می‌گیرد — یعنی رفتار پیش‌فرض دقیقاً همان میانگین ساده‌ای است که تا امروز بود.
    indicator_weights: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # فعال‌سازی دو نفره: کسی که طرح را ساخته نمی‌تواند خودش فعالش کند. تغییر
    # قاعدهٔ نمره‌دهی کل سازمان نباید تصمیم یک نفرِ تنها باشد.
    activated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # حداکثر یک طرح فعال — با ایندکس یکتای جزئی، به همان دلیلی که
        # uq_single_open_period وجود دارد: بررسی در کد در برابر دو درخواست
        # هم‌زمان بی‌فایده است.
        Index(
            "uq_single_active_scheme",
            "status",
            unique=True,
            postgresql_where=(status == SchemeStatus.active),
        ),
    )
