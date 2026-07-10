from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.api.routers.personnel import _can_view_personnel
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.enums import EvaluationStatus, PersonnelStatus, UserRole
from app.models.evaluation import EvaluationRecord, EvaluationScore
from app.models.evaluation_access import EvaluationAccess
from app.models.indicator import Indicator
from app.models.personnel import Personnel
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.schemas.dashboard import (
    DashboardOverview,
    EvaluatorStat,
    IndicatorStat,
    InProgressEvaluation,
    PersonStat,
    PipelineStat,
    RadarPoint,
    RoleOverview,
    RoleOverviewCard,
    TrendPoint,
    UnitStat,
)
from app.schemas.notification import ExpiringContract

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

_FINALIZED = EvaluationRecord.status == EvaluationStatus.finalized


@router.get("/overview", response_model=DashboardOverview)
def overview(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> DashboardOverview:
    """همه آمارها با تجمیع SQL محاسبه می‌شوند؛ نسخه قبلی کل جدول‌ها را در حافظه
    بارگذاری می‌کرد و به ازای هر رکورد یک کوئری جدا برای امتیازها می‌زد (N+1)."""
    total = db.scalar(select(func.count()).select_from(EvaluationRecord).where(_FINALIZED)) or 0
    avg_raw = db.scalar(select(func.avg(EvaluationRecord.final_weighted_pct)).where(_FINALIZED))
    avg_final = round(float(avg_raw), 1) if avg_raw is not None else None

    unit_rows = db.execute(
        select(
            Personnel.org_unit,
            func.avg(EvaluationRecord.final_weighted_pct),
            func.count(),
        )
        .join(Personnel, Personnel.id == EvaluationRecord.subject_personnel_id)
        .where(_FINALIZED, EvaluationRecord.final_weighted_pct.is_not(None))
        .group_by(Personnel.org_unit)
    ).all()
    by_org_unit = [
        UnitStat(org_unit=unit, avg_final_pct=round(float(avg), 1), count=count)
        for unit, avg, count in unit_rows
    ]

    subordinate_counts = dict(
        db.execute(
            select(EvaluationAccess.unit_supervisor_user_id, func.count())
            .where(EvaluationAccess.unit_supervisor_user_id.is_not(None))
            .group_by(EvaluationAccess.unit_supervisor_user_id)
        ).all()
    )

    evaluator_rows = db.execute(
        select(
            User.id,
            User.username,
            func.avg(EvaluationRecord.final_weighted_pct),
            func.count(),
        )
        .join(EvaluationRecord, EvaluationRecord.unit_supervisor_user_id == User.id)
        .where(_FINALIZED, EvaluationRecord.final_weighted_pct.is_not(None))
        .group_by(User.id, User.username)
    ).all()
    by_evaluator = [
        EvaluatorStat(
            evaluator_user_id=uid,
            username=username,
            avg_final_pct=round(float(avg), 1),
            subordinate_count=subordinate_counts.get(uid, 0),
            evaluation_count=count,
        )
        for uid, username, avg, count in evaluator_rows
    ]

    indicator_rows = db.execute(
        select(Indicator.id, Indicator.category, func.avg(EvaluationScore.score))
        .join(EvaluationScore, EvaluationScore.indicator_id == Indicator.id)
        .join(EvaluationRecord, EvaluationRecord.id == EvaluationScore.evaluation_record_id)
        .where(_FINALIZED)
        .group_by(Indicator.id, Indicator.category)
        .order_by(func.avg(EvaluationScore.score))
        .limit(5)
    ).all()
    lowest_by_indicator = [
        IndicatorStat(indicator_id=iid, category=category, avg_score=round(float(avg), 2))
        for iid, category, avg in indicator_rows
    ]

    lowest_by_unit = sorted(by_org_unit, key=lambda x: x.avg_final_pct)[:5]

    person_rows = db.execute(
        select(Personnel.id, Personnel.full_name, EvaluationRecord.final_weighted_pct)
        .join(Personnel, Personnel.id == EvaluationRecord.subject_personnel_id)
        .where(_FINALIZED, EvaluationRecord.final_weighted_pct.is_not(None))
        .order_by(EvaluationRecord.final_weighted_pct)
        .limit(5)
    ).all()
    lowest_by_person = [
        PersonStat(personnel_id=pid, full_name=name, final_weighted_pct=float(pct))
        for pid, name, pct in person_rows
    ]

    return DashboardOverview(
        total_evaluations=total,
        avg_final_pct=avg_final,
        by_org_unit=by_org_unit,
        by_evaluator=by_evaluator,
        lowest_by_indicator=lowest_by_indicator,
        lowest_by_unit=lowest_by_unit,
        lowest_by_person=lowest_by_person,
    )


@router.get("/pipeline", response_model=list[PipelineStat])
def pipeline(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> list[PipelineStat]:
    """قیف گردش‌کار: چند پرونده در هر وضعیت است و قدیمی‌ترین پرونده هر وضعیت از کی مانده."""
    rows = {
        status_value: (count, oldest)
        for status_value, count, oldest in db.execute(
            select(
                EvaluationRecord.status,
                func.count(),
                func.min(EvaluationRecord.created_at),
            ).group_by(EvaluationRecord.status)
        ).all()
    }
    return [
        PipelineStat(
            status=status_member,
            count=rows.get(status_member, (0, None))[0],
            oldest_created_at=rows.get(status_member, (0, None))[1],
        )
        for status_member in EvaluationStatus
    ]


@router.get("/expiring-contracts", response_model=list[ExpiringContract])
def expiring_contracts(
    days: int = Query(default=60, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> list[ExpiringContract]:
    """پرسنل فعالی که قراردادشان تا N روز آینده تمام می‌شود (یا منقضی شده)، به‌همراه
    این‌که آیا ارزیابی بازی برایشان در جریان است — هدف اصلی محصول: تصمیم به‌موقع تمدید."""
    today = date.today()
    horizon = today + timedelta(days=days)

    open_evaluation_exists = (
        select(EvaluationRecord.id)
        .where(
            EvaluationRecord.subject_personnel_id == Personnel.id,
            EvaluationRecord.status != EvaluationStatus.finalized,
        )
        .exists()
    )

    rows = db.execute(
        select(
            Personnel.id,
            Personnel.full_name,
            Personnel.org_unit,
            Personnel.contract_end_date,
            open_evaluation_exists.label("has_open"),
        )
        .where(
            Personnel.status == PersonnelStatus.active,
            Personnel.contract_end_date <= horizon,
        )
        .order_by(Personnel.contract_end_date)
    ).all()

    return [
        ExpiringContract(
            personnel_id=pid,
            full_name=name,
            org_unit=unit,
            contract_end_date=end_date,
            days_remaining=(end_date - today).days,
            has_open_evaluation=has_open,
        )
        for pid, name, unit, end_date, has_open in rows
    ]


@router.get("/personnel/{personnel_id}/radar", response_model=list[RadarPoint])
def personnel_radar(
    personnel_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[RadarPoint]:
    # HR همه را می‌بیند؛ ارزیاب‌ها (مسئول واحد/معاونت/مدیرعامل) فقط پرسنلی را که
    # در حوزهٔ دسترسی/ارزیابی خودشان است — تا پیش از نمره‌دهی روند فرد را ببینند.
    if not _can_view_personnel(db, personnel_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="دسترسی مجاز نیست")
    rows = db.execute(
        select(Indicator.category, func.avg(EvaluationScore.score))
        .join(EvaluationScore, EvaluationScore.indicator_id == Indicator.id)
        .join(EvaluationRecord, EvaluationRecord.id == EvaluationScore.evaluation_record_id)
        .where(_FINALIZED, EvaluationRecord.subject_personnel_id == personnel_id)
        .group_by(Indicator.category)
    ).all()
    return [RadarPoint(category=category, avg_score=round(float(avg), 2)) for category, avg in rows]


@router.get("/personnel/{personnel_id}/trend", response_model=list[TrendPoint])
def personnel_trend(
    personnel_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[TrendPoint]:
    if not _can_view_personnel(db, personnel_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="دسترسی مجاز نیست")
    records = db.scalars(
        select(EvaluationRecord)
        .where(
            _FINALIZED,
            EvaluationRecord.subject_personnel_id == personnel_id,
            EvaluationRecord.finalized_at.is_not(None),
        )
        .order_by(EvaluationRecord.finalized_at)
    )
    return [
        TrendPoint(
            evaluation_code=r.evaluation_code,
            finalized_at=r.finalized_at.isoformat(),
            final_weighted_pct=float(r.final_weighted_pct),
        )
        for r in records
    ]


@router.get(
    "/personnel/{personnel_id}/in-progress",
    response_model=InProgressEvaluation | None,
)
def personnel_in_progress(
    personnel_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> InProgressEvaluation | None:
    """ارزیابی باز (نهایی‌نشدهٔ) جاری این پرسنل را برمی‌گرداند تا در پروفایل، «مرحلهٔ
    فعلی» نمایش داده شود؛ اگر پرونده‌ای در جریان نباشد null برمی‌گردد. دسترسی مثل
    رادار/روند محدود است (HR همه، ارزیاب فقط حوزهٔ خودش)."""
    if not _can_view_personnel(db, personnel_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="دسترسی مجاز نیست")
    record = db.scalar(
        select(EvaluationRecord)
        .where(
            EvaluationRecord.subject_personnel_id == personnel_id,
            EvaluationRecord.status != EvaluationStatus.finalized,
        )
        .order_by(EvaluationRecord.created_at.desc())
    )
    if record is None:
        return None
    was_returned = (
        db.scalar(
            select(AuditLog.id)
            .where(
                AuditLog.event_type == "evaluation_returned",
                AuditLog.evaluation_record_id == record.id,
            )
            .limit(1)
        )
        is not None
    )
    return InProgressEvaluation(
        evaluation_id=record.id,
        evaluation_code=record.evaluation_code,
        status=record.status,
        was_returned=was_returned,
        created_at=record.created_at,
    )


def _count_records(db: Session, *conditions) -> int:
    return (
        db.scalar(
            select(func.count()).select_from(EvaluationRecord).where(*conditions)
        )
        or 0
    )


@router.get("/role-overview", response_model=RoleOverview)
def role_overview(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RoleOverview:
    """کاشی‌های خلاصهٔ داشبورد، متناسب با نقشِ کاربرِ واردشده — تا هر نقش در صفحهٔ
    اصلی خود یک نمای سریع از کارهای در انتظار و وضعیت پرونده‌هایش داشته باشد."""
    uid = current_user.id
    role = current_user.role
    cards: list[RoleOverviewCard] = []

    if role == UserRole.unit_supervisor:
        subordinates = (
            db.scalar(
                select(func.count())
                .select_from(EvaluationAccess)
                .where(EvaluationAccess.unit_supervisor_user_id == uid)
            )
            or 0
        )
        mine = EvaluationRecord.unit_supervisor_user_id == uid
        cards = [
            RoleOverviewCard(key="subordinates", label="افراد زیرمجموعه", value=subordinates, tone="neutral"),
            RoleOverviewCard(
                key="drafts",
                label="پیش‌نویس باز",
                value=_count_records(db, mine, EvaluationRecord.status == EvaluationStatus.draft),
                tone="amber",
            ),
            RoleOverviewCard(
                key="in_review",
                label="در جریان تأیید",
                value=_count_records(
                    db,
                    mine,
                    EvaluationRecord.status.in_(
                        [
                            EvaluationStatus.submitted,
                            EvaluationStatus.hr_approved,
                            EvaluationStatus.deputy_approved,
                        ]
                    ),
                ),
                tone="pulse",
            ),
            RoleOverviewCard(
                key="finalized",
                label="نهایی‌شده",
                value=_count_records(db, mine, _FINALIZED),
                tone="green",
            ),
        ]
    elif role == UserRole.deputy:
        mine = EvaluationRecord.deputy_user_id == uid
        cards = [
            RoleOverviewCard(
                key="awaiting_me",
                label="در انتظار تأیید من",
                value=_count_records(
                    db,
                    mine,
                    EvaluationRecord.status == EvaluationStatus.hr_approved,
                    EvaluationRecord.unit_supervisor_user_id.is_not(None),
                ),
                tone="amber",
            ),
            RoleOverviewCard(
                key="manager_scoring",
                label="امتیازدهی مدیر (با من)",
                value=_count_records(
                    db,
                    mine,
                    EvaluationRecord.status == EvaluationStatus.hr_approved,
                    EvaluationRecord.unit_supervisor_user_id.is_(None),
                ),
                tone="pulse",
            ),
            RoleOverviewCard(
                key="finalized",
                label="نهایی‌شده (حوزهٔ من)",
                value=_count_records(db, mine, _FINALIZED),
                tone="green",
            ),
        ]
    elif role == UserRole.ceo:
        mine = EvaluationRecord.ceo_user_id == uid
        cards = [
            RoleOverviewCard(
                key="awaiting_me",
                label="در انتظار تأیید نهایی",
                value=_count_records(
                    db, mine, EvaluationRecord.status == EvaluationStatus.deputy_approved
                ),
                tone="amber",
            ),
            RoleOverviewCard(
                key="finalized",
                label="نهایی‌شده (حوزهٔ من)",
                value=_count_records(db, mine, _FINALIZED),
                tone="green",
            ),
            RoleOverviewCard(
                key="total",
                label="کل پرونده‌های من",
                value=_count_records(db, mine),
                tone="neutral",
            ),
        ]
    elif role == UserRole.hr:
        personnel_count = (
            db.scalar(select(func.count()).select_from(Personnel)) or 0
        )
        cards = [
            RoleOverviewCard(
                key="awaiting_hr",
                label="در انتظار بررسی منابع انسانی",
                value=_count_records(db, EvaluationRecord.status == EvaluationStatus.submitted),
                tone="amber",
            ),
            RoleOverviewCard(
                key="open",
                label="پرونده‌های باز",
                value=_count_records(db, EvaluationRecord.status != EvaluationStatus.finalized),
                tone="pulse",
            ),
            RoleOverviewCard(
                key="finalized",
                label="نهایی‌شده",
                value=_count_records(db, _FINALIZED),
                tone="green",
            ),
            RoleOverviewCard(key="personnel", label="کل پرسنل", value=personnel_count, tone="neutral"),
        ]
    elif role == UserRole.employee and current_user.personnel_id is not None:
        pid = current_user.personnel_id
        mine = EvaluationRecord.subject_personnel_id == pid
        avg = db.scalar(
            select(func.avg(EvaluationRecord.final_weighted_pct)).where(mine, _FINALIZED)
        )
        cards = [
            RoleOverviewCard(
                key="finalized",
                label="ارزیابی‌های نهایی‌شده",
                value=_count_records(db, mine, _FINALIZED),
                tone="neutral",
            ),
            RoleOverviewCard(
                key="avg",
                label="میانگین امتیاز نهایی (٪)",
                value=round(float(avg), 1) if avg is not None else 0,
                tone="green",
            ),
            RoleOverviewCard(
                key="pending_ack",
                label="در انتظار رؤیت شما",
                value=_count_records(
                    db, mine, _FINALIZED, EvaluationRecord.acknowledged_at.is_(None)
                ),
                tone="amber",
            ),
        ]

    return RoleOverview(role=role.value, cards=cards)
