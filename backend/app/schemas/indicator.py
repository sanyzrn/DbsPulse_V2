from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.text_limits import INDICATOR_CATEGORY_MAX, INDICATOR_DESCRIPTION_MAX
from app.models.enums import IndicatorSection


class IndicatorCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    section: IndicatorSection
    category: str = Field(min_length=1, max_length=INDICATOR_CATEGORY_MAX)
    description: str = Field(min_length=1, max_length=INDICATOR_DESCRIPTION_MAX)
    display_order: int = Field(default=0, ge=0)


class IndicatorUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category: str | None = Field(default=None, min_length=1, max_length=INDICATOR_CATEGORY_MAX)
    description: str | None = Field(default=None, min_length=1, max_length=INDICATOR_DESCRIPTION_MAX)
    display_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    #: تنها راه ویرایشِ متنِ شاخصی که قبلاً نمره خورده (P1-05).
    #:
    #: سامانه نمی‌تواند «اصلاح غلط املایی» را از «سؤال را عوض کردم» تشخیص بدهد،
    #: ولی آدمی که تایپ می‌کند می‌تواند. پس به‌جای حدس زدن، از او می‌پرسیم — و
    #: چون باید دلیل بنویسد، ادعایش در لاگ ممیزی ثبت و قابل بازبینی می‌ماند.
    wording_fix_reason: str | None = Field(default=None, min_length=3, max_length=500)


class IndicatorReplace(BaseModel):
    """جایگزینی یک شاخص با نسخهٔ تازه‌اش — وقتی *معنا* عوض می‌شود.

    شاخص قدیمی غیرفعال می‌شود ولی می‌ماند، و شاخص تازه شناسهٔ خودش را می‌گیرد.
    این تنها راهی است که تحلیل بتواند به آن اعتماد کند: اگر معنای یک شناسه هرگز
    عوض نشود، نموداری که بر اساس شناسه گروه‌بندی می‌کند هیچ‌وقت دو سؤال متفاوت را
    یکی نمی‌بیند.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    category: str = Field(min_length=1, max_length=INDICATOR_CATEGORY_MAX)
    description: str = Field(min_length=1, max_length=INDICATOR_DESCRIPTION_MAX)
    reason: str = Field(min_length=3, max_length=500)


class FrameworkImpact(BaseModel):
    """آنچه منابع انسانی باید *قبل از* تغییر عضویت بداند."""

    version: int
    member_count: int
    #: پرونده‌های بازی که امتیاز خورده‌اند — با نسخهٔ فعلی خودشان بسته می‌شوند
    frozen_open_records: int
    #: پرونده‌های بازِ دست‌نخورده — به نسخهٔ تازه منتقل می‌شوند
    movable_open_records: int


class IndicatorReorder(BaseModel):
    """ترتیب جدید شاخص‌های یک بخش؛ ordered_ids باید دقیقاً همان مجموعهٔ شناسه‌های
    آن بخش باشد، به ترتیب دلخواه کاربر (drag-and-drop)."""

    section: IndicatorSection
    ordered_ids: list[int] = Field(min_length=1)


class IndicatorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    section: IndicatorSection
    category: str
    description: str
    display_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    #: به این شاخص در چند ارزیابی نمره داده شده (P1-05).
    #:
    #: تفاوت «۰» و «۲۳۰» تفاوت یک ویرایش بی‌ضرر و بازنویسی معنای دو سال تاریخ
    #: است. تا امروز کسی که ویرایش می‌کرد این عدد را نمی‌دید — و نتیجه‌اش دقیقاً
    #: همان تصمیم‌های بی‌خبرانه‌ای بود که این تغییر برای جلوگیری از آن‌هاست.
    usage_count: int = 0
