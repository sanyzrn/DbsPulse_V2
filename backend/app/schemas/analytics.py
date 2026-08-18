"""شکل پاسخ نماهای تحلیلیِ نقش‌محور (P2-01).

دو نما، دو مخاطب، دو قاعدهٔ متفاوت برای افشا:

* **ارزیاب** دربارهٔ *خودش* می‌پرسد. آمار خودش سرکوب نمی‌شود — او همان نمره‌ها را
  خودش داده و چیزی «کشف» نمی‌کند. ولی هر عددی که به آن *مقایسه* می‌شود (میانگین
  سازمان، میانگین یک شاخص در کل سازمان) آمار گروهی دیگران است و از سرکوب کوهورت
  رد می‌شود.
* **مدیر ارشد** فقط تجمیع می‌بیند. هیچ نام و هیچ شناسهٔ فردی در این پاسخ نیست —
  نه در نمونهٔ کد و نه در عمل. این همان چیزی است که «باز کردن آنالیتیکس» را از
  «دور زدن کنترل دسترسی» جدا می‌کند.
"""
from pydantic import BaseModel


class ScoreDistributionBucket(BaseModel):
    """چند بار این امتیاز داده شده — من در برابر بقیه.

    سهم درصدی است که خوانده می‌شود، نه تعداد: ارزیابی که ۴۰ نمره داده را نمی‌شود
    با سازمانی که ۴۰۰۰ نمره دارد از روی تعداد مقایسه کرد.
    """

    score: int
    my_count: int
    my_share_pct: float
    org_share_pct: float | None


class IndicatorGap(BaseModel):
    """فاصلهٔ میانگین من با میانگین سازمان، روی یک شاخص."""

    indicator_id: int
    category: str
    description: str
    my_avg: float | None
    org_avg: float | None
    my_count: int


class MyScoringProfile(BaseModel):
    """آینهٔ ارزیاب: «من سخت‌گیرم یا آسان‌گیر، و کجا؟»

    مفیدترین بازخوردی که یک ارزیاب می‌تواند بگیرد، و تا امروز هیچ نقشی جز
    منابع انسانی به آن دسترسی نداشت.
    """

    my_score_count: int
    my_avg_score: float | None
    org_avg_score: float | None
    #: چند *نفر* (به‌جز افراد خودم) در «میانگین سازمان» سهم دارند. عمداً تعداد
    #: نفر است نه تعداد ردیف نمره: هر ارزیابی حدود بیست ردیف دارد، پس عددِ ردیفی
    #: پشتوانهٔ آمار را بیست برابر بزرگ‌تر از آن‌چه هست نشان می‌دهد — و همان عدد
    #: است که آستانهٔ سرکوب رویش اعمال می‌شود.
    org_people_count: int
    distribution: list[ScoreDistributionBucket]
    indicator_gaps: list[IndicatorGap]
    #: چه سهمی از نمره‌های من شواهد نوشته دارد. قاعدهٔ اجباری فقط ۱ و ۵ را
    #: می‌گیرد؛ این عدد کیفیت *داوطلبانه* را نشان می‌دهد.
    evidence_rate_pct: float | None
    #: میانهٔ روزهایی که پرونده‌های من در مرحلهٔ خودم مانده‌اند تا ثبت شوند
    median_days_in_my_stage: float | None
    #: پرونده‌های بازِ من که همین حالا منتظر اقدام خودم‌اند
    open_with_me: int


class UnitPerformance(BaseModel):
    org_unit: str
    avg_final_pct: float | None
    count: int


class SitePerformance(BaseModel):
    """کارنامهٔ یک محل (دفتر مرکزی، کارخانه، …).

    از روی همان `org_unit` ساخته می‌شود؛ توضیحِ قرارداد در
    `app/services/org_unit.py`.
    """

    site: str
    avg_final_pct: float | None
    count: int


class RecommendationSlice(BaseModel):
    """ترکیب نتیجهٔ پیشنهادی — همان چیزی که به تصمیم تمدید قرارداد ترجمه می‌شود."""

    recommendation: str
    count: int
    share_pct: float


class CycleTime(BaseModel):
    """چقدر طول می‌کشد یک پرونده از آغاز تا نهایی‌شدن."""

    finalized_count: int
    median_days: float | None
    p90_days: float | None
    #: قدیمی‌ترین پروندهٔ بازِ سازمان چند روز است در همان مرحله مانده
    oldest_open_stage_days: float | None
    open_count: int


class ContractExposure(BaseModel):
    """ریسک تمدید: چند نفر قراردادشان رو به پایان است و چند نفرشان هنوز
    ارزیابی نشده‌اند — یعنی تصمیم بدون داده گرفته می‌شود."""

    horizon_days: int
    expiring: int
    without_finalized_evaluation: int


class ExecutiveOverview(BaseModel):
    total_finalized: int
    avg_final_pct: float | None
    by_org_unit: list[UnitPerformance]
    #: خالی می‌ماند اگر هیچ واحدی جداکنندهٔ محل نداشته باشد — یعنی سازمان یک
    #: محل بیشتر ندارد و این تفکیک برایش معنا ندارد.
    by_site: list[SitePerformance]
    recommendation_mix: list[RecommendationSlice]
    cycle_time: CycleTime
    contract_exposure: list[ContractExposure]
