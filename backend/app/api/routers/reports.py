"""گزارش‌های تحلیلی فیلترشوندهٔ منابع انسانی.

همهٔ گزارش‌ها فقط روی ارزیابی‌های «نهایی‌شده» کار می‌کنند (تنها امتیازهای قطعی) و یک
مجموعهٔ مشترک از فیلترهای ترکیب‌پذیر می‌پذیرند: دورهٔ ارزیابی، واحد سازمانی، پرسنل
مشخص، بازهٔ تاریخ شروع ارزیابی، وضعیت پرسنل و بازهٔ تاریخ پایان قرارداد (برای دیدن
افرادِ رو به اتمام/منقضی). خروجی Excel ترکیبی هم دقیقاً از همین فیلترها پیروی می‌کند.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.enums import EvaluationStatus, PersonnelStatus, UserRole
from app.models.evaluation import EvaluationRecord, EvaluationScore
from app.models.indicator import Indicator
from app.models.personnel import Personnel
from app.schemas.auth import CurrentUser
from app.schemas.dashboard import (
    EmployeeEvaluationPoint,
    EmployeeVsUnit,
    IndicatorBreakdown,
    IndicatorReportStat,
    ReportSummary,
    UnitIndicatorStat,
    UnitStat,
)
from app.services.excel import build_report_workbook
from app.services.privacy import suppressed_avg

router = APIRouter(prefix="/api/dashboard/report", tags=["reports"])

_FINALIZED = EvaluationRecord.status == EvaluationStatus.finalized


def _record_conditions(
    *,
    period_id: int | None,
    org_unit: str | None,
    personnel_id: int | None,
    created_from: date | None,
    created_to: date | None,
    personnel_status: PersonnelStatus | None,
    contract_end_from: date | None,
    contract_end_to: date | None,
) -> list:
    """شرط‌های WHERE مشترک همهٔ گزارش‌ها (بجز فیلتر شاخص). فرض بر این است که کوئری
    فراخوان، Personnel را به EvaluationRecord join کرده است."""
    conditions = [_FINALIZED]
    if period_id is not None:
        conditions.append(EvaluationRecord.period_id == period_id)
    if org_unit:
        conditions.append(Personnel.org_unit == org_unit)
    if personnel_id is not None:
        conditions.append(EvaluationRecord.subject_personnel_id == personnel_id)
    if created_from is not None:
        conditions.append(EvaluationRecord.created_at >= created_from)
    if created_to is not None:
        conditions.append(EvaluationRecord.created_at < created_to + timedelta(days=1))
    if personnel_status is not None:
        conditions.append(Personnel.status == personnel_status)
    if contract_end_from is not None:
        conditions.append(Personnel.contract_end_date >= contract_end_from)
    if contract_end_to is not None:
        conditions.append(Personnel.contract_end_date <= contract_end_to)
    return conditions


class _Filters:
    """جمع‌کنندهٔ پارامترهای فیلتر مشترک به‌عنوان یک وابستگی FastAPI."""

    def __init__(
        self,
        period_id: int | None = None,
        org_unit: str | None = None,
        personnel_id: int | None = None,
        created_from: date | None = None,
        created_to: date | None = None,
        personnel_status: PersonnelStatus | None = Query(default=None, alias="status"),
        contract_end_from: date | None = None,
        contract_end_to: date | None = None,
    ) -> None:
        if created_from is not None and created_to is not None and created_from > created_to:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="تاریخ شروع بازه نمی‌تواند بعد از تاریخ پایان آن باشد",
            )
        self.period_id = period_id
        self.org_unit = org_unit
        self.personnel_id = personnel_id
        self.created_from = created_from
        self.created_to = created_to
        self.personnel_status = personnel_status
        self.contract_end_from = contract_end_from
        self.contract_end_to = contract_end_to

    def conditions(self) -> list:
        return _record_conditions(
            period_id=self.period_id,
            org_unit=self.org_unit,
            personnel_id=self.personnel_id,
            created_from=self.created_from,
            created_to=self.created_to,
            personnel_status=self.personnel_status,
            contract_end_from=self.contract_end_from,
            contract_end_to=self.contract_end_to,
        )


def _summary_data(db: Session, filters: _Filters) -> ReportSummary:
    conditions = filters.conditions()

    base = (
        select(EvaluationRecord.id, EvaluationRecord.final_weighted_pct)
        .join(Personnel, Personnel.id == EvaluationRecord.subject_personnel_id)
        .where(*conditions)
    ).subquery()
    total = db.scalar(select(func.count()).select_from(base)) or 0
    avg_raw = db.scalar(select(func.avg(base.c.final_weighted_pct)))
    avg_final = round(float(avg_raw), 1) if avg_raw is not None else None
    # سرجمع فقط وقتی سرکوب می‌شود که کاربر یک فرد مشخص را نام نبرده باشد؛ اگر خودش
    # personnel_id داده، می‌داند دارد به دادهٔ چه کسی نگاه می‌کند.
    if filters.personnel_id is None:
        avg_final = suppressed_avg(avg_final, total)

    unit_rows = db.execute(
        select(Personnel.org_unit, func.avg(EvaluationRecord.final_weighted_pct), func.count())
        .join(Personnel, Personnel.id == EvaluationRecord.subject_personnel_id)
        .where(*conditions, EvaluationRecord.final_weighted_pct.is_not(None))
        .group_by(Personnel.org_unit)
        .order_by(func.avg(EvaluationRecord.final_weighted_pct).desc())
    ).all()
    by_org_unit = [
        UnitStat(
            org_unit=unit,
            avg_final_pct=suppressed_avg(round(float(avg), 1), count),
            count=count,
        )
        for unit, avg, count in unit_rows
    ]

    indicator_rows = db.execute(
        select(
            Indicator.id,
            Indicator.category,
            Indicator.description,
            Indicator.section,
            func.avg(EvaluationScore.score),
            func.count(),
        )
        .join(EvaluationScore, EvaluationScore.indicator_id == Indicator.id)
        .join(EvaluationRecord, EvaluationRecord.id == EvaluationScore.evaluation_record_id)
        .join(Personnel, Personnel.id == EvaluationRecord.subject_personnel_id)
        .where(*conditions)
        .group_by(Indicator.id, Indicator.category, Indicator.description, Indicator.section, Indicator.display_order)
        .order_by(Indicator.section, Indicator.display_order)
    ).all()
    by_indicator = [
        IndicatorReportStat(
            indicator_id=iid,
            category=category,
            description=description,
            section=section.value,
            avg_score=suppressed_avg(round(float(avg), 2), count),
            count=count,
        )
        for iid, category, description, section, avg, count in indicator_rows
    ]

    return ReportSummary(
        total_evaluations=total,
        avg_final_pct=avg_final,
        by_org_unit=by_org_unit,
        by_indicator=by_indicator,
    )


@router.get("/summary", response_model=ReportSummary)
def report_summary(
    filters: _Filters = Depends(),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> ReportSummary:
    return _summary_data(db, filters)


@router.get("/indicator/{indicator_id}", response_model=IndicatorBreakdown)
def indicator_breakdown(
    indicator_id: int,
    filters: _Filters = Depends(),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> IndicatorBreakdown:
    """ریز یک شاخص خاص: میانگین کلی و به‌تفکیک واحد سازمانی، با همان فیلترهای صفحه."""
    indicator = db.get(Indicator, indicator_id)
    if indicator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="شاخص یافت نشد")

    conditions = filters.conditions()
    score_join = (
        select(EvaluationScore.score, Personnel.org_unit)
        .join(EvaluationRecord, EvaluationRecord.id == EvaluationScore.evaluation_record_id)
        .join(Personnel, Personnel.id == EvaluationRecord.subject_personnel_id)
        .where(*conditions, EvaluationScore.indicator_id == indicator_id)
    ).subquery()

    overall_raw = db.scalar(select(func.avg(score_join.c.score)))
    overall_avg = round(float(overall_raw), 2) if overall_raw is not None else None
    total = db.scalar(select(func.count()).select_from(score_join)) or 0
    if filters.personnel_id is None:
        overall_avg = suppressed_avg(overall_avg, total)

    unit_rows = db.execute(
        select(score_join.c.org_unit, func.avg(score_join.c.score), func.count())
        .group_by(score_join.c.org_unit)
        .order_by(func.avg(score_join.c.score).desc())
    ).all()
    by_org_unit = [
        UnitIndicatorStat(
            org_unit=unit, avg_score=suppressed_avg(round(float(avg), 2), count), count=count
        )
        for unit, avg, count in unit_rows
    ]

    return IndicatorBreakdown(
        indicator_id=indicator.id,
        category=indicator.category,
        description=indicator.description,
        overall_avg=overall_avg,
        count=total,
        by_org_unit=by_org_unit,
    )


@router.get("/employee-vs-unit", response_model=EmployeeVsUnit)
def employee_vs_unit(
    personnel_id: int = Query(...),
    period_id: int | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> EmployeeVsUnit:
    """امتیاز فرد در برابر میانگین واحد سازمانی‌اش برای همان دوره/بازه — تا مشخص شود
    فرد بالای میانگین واحد است یا پایین آن."""
    personnel = db.get(Personnel, personnel_id)
    if personnel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")

    def _range(conds: list) -> list:
        if period_id is not None:
            conds.append(EvaluationRecord.period_id == period_id)
        if created_from is not None:
            conds.append(EvaluationRecord.created_at >= created_from)
        if created_to is not None:
            conds.append(EvaluationRecord.created_at < created_to + timedelta(days=1))
        return conds

    # امتیازهای خودِ فرد
    emp_records = db.scalars(
        select(EvaluationRecord)
        .where(
            *_range([_FINALIZED, EvaluationRecord.subject_personnel_id == personnel_id]),
            EvaluationRecord.final_weighted_pct.is_not(None),
        )
        .order_by(EvaluationRecord.finalized_at)
    ).all()
    per_evaluation = [
        EmployeeEvaluationPoint(
            evaluation_code=r.evaluation_code,
            finalized_at=r.finalized_at.isoformat() if r.finalized_at else "",
            final_weighted_pct=float(r.final_weighted_pct),
        )
        for r in emp_records
    ]
    employee_avg = (
        round(sum(p.final_weighted_pct for p in per_evaluation) / len(per_evaluation), 1)
        if per_evaluation
        else None
    )

    # میانگین کل واحد سازمانی همان فرد
    unit_conditions = _range(
        [
            _FINALIZED,
            Personnel.org_unit == personnel.org_unit,
            EvaluationRecord.final_weighted_pct.is_not(None),
        ]
    )
    unit_stats = db.execute(
        select(func.avg(EvaluationRecord.final_weighted_pct), func.count())
        .join(Personnel, Personnel.id == EvaluationRecord.subject_personnel_id)
        .where(*unit_conditions)
    ).one()
    unit_count = unit_stats[1] or 0
    # میانگین واحد یک آمار گروهی است — اگر واحد یکی-دو نفر باشد، «میانگین واحد» عملاً
    # امتیاز همان یکی-دو نفر است. سری امتیازهای خودِ فرد (per_evaluation) سرکوب
    # نمی‌شود؛ کاربر خودش نام او را داده و چیز تازه‌ای افشا نمی‌شود.
    unit_avg = suppressed_avg(
        round(float(unit_stats[0]), 1) if unit_stats[0] is not None else None, unit_count
    )

    return EmployeeVsUnit(
        personnel_id=personnel.id,
        full_name=personnel.full_name,
        org_unit=personnel.org_unit,
        employee_avg=employee_avg,
        unit_avg=unit_avg,
        evaluation_count=len(per_evaluation),
        unit_evaluation_count=unit_count,
        per_evaluation=per_evaluation,
    )


@router.get("/export.xlsx")
def export_report_excel(
    filters: _Filters = Depends(),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> Response:
    """خروجی Excel ترکیبی: یک فایل با برگه‌های «خلاصه»، «میانگین به‌تفکیک واحد» و
    «میانگین به‌تفکیک شاخص»، دقیقاً برای فیلترهای فعال."""
    summary = _summary_data(db, filters)
    content = build_report_workbook(
        total=summary.total_evaluations,
        avg_final_pct=summary.avg_final_pct,
        by_org_unit=[(u.org_unit, u.avg_final_pct, u.count) for u in summary.by_org_unit],
        by_indicator=[
            (i.category, i.description, i.avg_score, i.count) for i in summary.by_indicator
        ],
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="hr-report.xlsx"'},
    )
