from datetime import datetime

from pydantic import BaseModel

from app.models.enums import EvaluationStatus


class UnitStat(BaseModel):
    org_unit: str
    avg_final_pct: float
    count: int


class EvaluatorStat(BaseModel):
    evaluator_user_id: int
    username: str
    avg_final_pct: float
    subordinate_count: int
    evaluation_count: int


class IndicatorStat(BaseModel):
    indicator_id: int
    category: str
    avg_score: float


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
