from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import EvaluationStatus


class UnitStat(BaseModel):
    org_unit: str
    # None یعنی «سرکوب‌شده»: جمعیت این واحد کمتر از آستانهٔ کوهورت است و
    # نمایش میانگینش عملاً افشای امتیاز فرد بود (P1-08).
    avg_final_pct: float | None
    count: int
    #: تفکیک همان میانگین به دو بخشِ فرم. واحدی که نمرهٔ کلش خوب است ممکن است
    #: در یکی از دو بخش ضعیف باشد و در دیگری قوی — و عددِ کل آن را پنهان می‌کند.
    avg_general_pct: float | None = None
    avg_specialized_pct: float | None = None
    #: محل (دفتر مرکزی / کارخانه / مدرپ‌ها)، برای فیلتر کردن.
    site: str | None = None


class EvaluatorStat(BaseModel):
    evaluator_user_id: int
    username: str
    # نام کامل، چون این جدول را آدم می‌خواند نه سامانه: «sup_it» به کارشناس
    # منابع انسانی نمی‌گوید کدام ارزیاب سخت‌گیرتر بوده است.
    full_name: str | None = None
    avg_final_pct: float | None
    subordinate_count: int
    evaluation_count: int


class IndicatorStat(BaseModel):
    indicator_id: int
    category: str
    #: شرحِ خودِ شاخص. چند شاخص می‌توانند یک «دسته» داشته باشند («بهبود مستمر»
    #: دو شاخص دارد)، و فهرستی که فقط دسته را نشان بدهد دو ردیفِ کاملاً یکسان
    #: می‌سازد که خواننده نمی‌داند کدام کدام است.
    description: str = ""
    avg_score: float | None


class PersonStat(BaseModel):
    personnel_id: int
    full_name: str
    final_weighted_pct: float
    org_unit: str = ""
    site: str | None = None


class OutcomeMix(BaseModel):
    """چند درصد افراد کجای طیف‌اند.

    مرزها از خودِ «طرح نمره‌دهی» می‌آیند، نه از عددی که این‌جا نوشته شده باشد:
    «نیازمند بهبود» همان بازه‌ای است که سامانه برایش برنامهٔ بهبود می‌سازد، و
    «مطلوب» بالاترین بندِ همان طرح است. عددِ ثابت در کد یعنی سازمانی که قواعدش
    را عوض می‌کند، گزارشی می‌بیند که با قواعد خودش نمی‌خواند.
    """

    strong_pct: float | None
    needs_improvement_pct: float | None
    #: مرزهایی که این دو درصد از رویشان حساب شده‌اند — تا خواننده بداند «مطلوب»
    #: یعنی چند.
    strong_threshold_pct: float
    improvement_threshold_pct: float
    people_counted: int


class DashboardOverview(BaseModel):
    total_evaluations: int
    avg_final_pct: float | None
    outcome_mix: OutcomeMix
    by_org_unit: list[UnitStat]
    by_evaluator: list[EvaluatorStat]
    lowest_by_indicator: list[IndicatorStat]
    highest_by_indicator: list[IndicatorStat]
    lowest_by_specialized_indicator: list[IndicatorStat]
    highest_by_specialized_indicator: list[IndicatorStat]
    lowest_by_unit: list[UnitStat]
    lowest_by_person: list[PersonStat]


class RadarPoint(BaseModel):
    category: str
    avg_score: float


class TrendPoint(BaseModel):
    evaluation_code: str
    finalized_at: str
    final_weighted_pct: float


class PipelineStat(BaseModel):
    """تعداد پرونده‌ها در هر وضعیت گردش‌کار + قدیمی‌ترین پرونده باز آن وضعیت."""

    status: EvaluationStatus
    count: int
    oldest_created_at: datetime | None


class StageOwnerStat(BaseModel):
    """آمار یک *شخص* در یک مرحله.

    «معاونت کند است» یک جملهٔ بی‌مصرف است وقتی سه معاون داری. این تفکیک همان
    جمله را به چیزی تبدیل می‌کند که می‌شود دربارهٔ آن کاری کرد.
    """

    name: str
    total: int
    active: int
    closed: int
    avg_dwell_days: float | None
    longest_active_days: float | None


class StageStat(BaseModel):
    status: EvaluationStatus
    #: «الان روی میزِ چه کسی است» — نه اینکه چه کسی کارش را کرده.
    holder: str
    #: چند پروندهٔ *متمایز* تا حالا از این مرحله گذشته یا این‌جاست.
    total: int
    active: int
    closed: int
    #: چند بار *ورود* به این مرحله رخ داده. بیشتر بودنش از `total` یعنی پرونده‌ها
    #: به این‌جا برمی‌گردند.
    passes: int
    share_pct: float
    #: میانگین فقط روی ماندن‌های تمام‌شده. `None` یعنی هنوز هیچ پرونده‌ای از این
    #: مرحله رد نشده — که با «صفر روز» یکی نیست.
    avg_dwell_days: float | None
    longest_active_days: float | None
    by_owner: list[StageOwnerStat]


class PeriodTrendPoint(BaseModel):
    """میانگین سازمان در یک دورهٔ ارزیابی.

    یک عددِ امروز نمی‌گوید سازمان دارد بهتر می‌شود یا بدتر. سه عدد پشت سر هم
    می‌گویند — و همان چیزی است که مدیر از یک گزارش سالانه می‌خواهد.
    """

    period_id: int | None
    name: str
    starts_on: date | None
    avg_final_pct: float | None
    count: int


class RoleOverviewCard(BaseModel):
    """یک کاشیِ خلاصهٔ داشبورد نقش؛ tone برای رنگ‌بندی سمت فرانت است."""

    key: str
    label: str
    value: float
    tone: str  # neutral | amber | pulse | green
    hint: str | None = None
    #: واحدی که بعد از عدد می‌آید («٪»). بدون این، «۵۵» و «۵۵٪» یک شکل دیده
    #: می‌شدند و کاشیِ درصد از کاشیِ تعداد قابل تشخیص نبود.
    suffix: str | None = None


class RoleOverview(BaseModel):
    role: str
    cards: list[RoleOverviewCard]


class InProgressEvaluation(BaseModel):
    """ارزیابی باز (نهایی‌نشدهٔ) جاری یک پرسنل، برای نمایش «مرحلهٔ فعلی» در پروفایل او."""

    evaluation_id: int
    evaluation_code: str
    status: EvaluationStatus
    was_returned: bool
    created_at: datetime


# ─────────────────────────── گزارش‌های تحلیلی فیلترشوندهٔ HR ───────────────────────────


class IndicatorReportStat(BaseModel):
    """میانگین امتیاز یک شاخص در مجموعهٔ ارزیابی‌های فیلترشده (از ۵)."""

    indicator_id: int
    category: str
    description: str
    section: str
    avg_score: float | None
    count: int


class ReportSummary(BaseModel):
    """خلاصهٔ گزارش برای فیلترهای اعمال‌شده: مجموع، میانگین، به‌تفکیک واحد و شاخص."""

    total_evaluations: int
    avg_final_pct: float | None
    by_org_unit: list[UnitStat]
    by_indicator: list[IndicatorReportStat]


class UnitIndicatorStat(BaseModel):
    org_unit: str
    avg_score: float | None
    count: int


class IndicatorBreakdown(BaseModel):
    """ریز یک شاخص خاص به‌تفکیک واحد سازمانی (مقایسهٔ واحدها روی همان شاخص)."""

    indicator_id: int
    category: str
    description: str
    overall_avg: float | None
    count: int
    by_org_unit: list[UnitIndicatorStat]


class EmployeeEvaluationPoint(BaseModel):
    evaluation_code: str
    finalized_at: str
    final_weighted_pct: float


class EmployeeVsUnit(BaseModel):
    """مقایسهٔ امتیاز یک فرد با میانگین واحد سازمانی‌اش برای همان فیلترها."""

    personnel_id: int
    full_name: str
    org_unit: str
    employee_avg: float | None
    unit_avg: float | None
    evaluation_count: int
    unit_evaluation_count: int
    per_evaluation: list[EmployeeEvaluationPoint]
