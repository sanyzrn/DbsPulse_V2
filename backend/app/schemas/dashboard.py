from datetime import datetime

from pydantic import BaseModel

from app.models.enums import EvaluationStatus


class UnitStat(BaseModel):
    org_unit: str
    # None یعنی «سرکوب‌شده»: جمعیت این واحد کمتر از آستانهٔ کوهورت است و
    # نمایش میانگینش عملاً افشای امتیاز فرد بود (P1-08).
    avg_final_pct: float | None
    count: int


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
    avg_score: float | None


class PersonStat(BaseModel):
    personnel_id: int
    full_name: str
    final_weighted_pct: float


class DashboardOverview(BaseModel):
    total_evaluations: int
    avg_final_pct: float | None
    by_org_unit: list[UnitStat]
    by_evaluator: list[EvaluatorStat]
    lowest_by_indicator: list[IndicatorStat]
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


class RoleOverviewCard(BaseModel):
    """یک کاشیِ خلاصهٔ داشبورد نقش؛ tone برای رنگ‌بندی سمت فرانت است."""

    key: str
    label: str
    value: float
    tone: str  # neutral | amber | pulse | green
    hint: str | None = None


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
