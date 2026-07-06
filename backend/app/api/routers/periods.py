from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.enums import EvaluationStatus, PeriodStatus, PersonnelStatus, UserRole
from app.models.evaluation import EvaluationRecord
from app.models.evaluation_access import EvaluationAccess
from app.models.evaluation_period import EvaluationPeriod
from app.models.personnel import Personnel
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.schemas.period import NotStartedPersonnel, PeriodCreate, PeriodProgress, PeriodRead
from app.services.audit import log_event
from app.services.notifications import notify

router = APIRouter(prefix="/api/periods", tags=["periods"])


def _get_period_or_404(db: Session, period_id: int) -> EvaluationPeriod:
    period = db.get(EvaluationPeriod, period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="دوره ارزیابی یافت نشد")
    return period


@router.get("", response_model=list[PeriodRead])
def list_periods(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> list[EvaluationPeriod]:
    return list(
        db.scalars(select(EvaluationPeriod).order_by(EvaluationPeriod.created_at.desc()))
    )


@router.post("", response_model=PeriodRead, status_code=status.HTTP_201_CREATED)
def create_period(
    payload: PeriodCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> EvaluationPeriod:
    already_open = db.scalar(
        select(EvaluationPeriod).where(EvaluationPeriod.status == PeriodStatus.open)
    )
    if already_open is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"دوره «{already_open.name}» هنوز باز است؛ ابتدا آن را ببندید",
        )

    period = EvaluationPeriod(
        name=payload.name,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        status=PeriodStatus.open,
        created_by_user_id=current_user.id,
    )
    db.add(period)
    try:
        db.flush()
    except IntegrityError as exc:
        # دو درخواست هم‌زمان: ایندکس یکتای جزئی برنده را مشخص می‌کند
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="یک دوره باز دیگر هم‌زمان ساخته شد؛ ابتدا آن را ببندید",
        ) from exc

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="period_created",
        new_value={"id": period.id, "name": period.name},
    )
    # ارزیاب‌ها (مسئولان واحد و معاونت‌ها) از شروع دوره باخبر می‌شوند
    evaluator_ids = db.scalars(
        select(User.id).where(
            User.role.in_([UserRole.unit_supervisor, UserRole.deputy]),
            User.is_active.is_(True),
        )
    )
    notify(
        db,
        evaluator_ids,
        type_="period_opened",
        message=f"دوره ارزیابی «{period.name}» آغاز شد؛ ارزیابی افراد زیرمجموعه خود را شروع کنید",
        link="/",
    )
    db.commit()
    db.refresh(period)
    return period


@router.post("/{period_id}/close", response_model=PeriodRead)
def close_period(
    period_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> EvaluationPeriod:
    period = _get_period_or_404(db, period_id)
    if period.status != PeriodStatus.open:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="این دوره قبلاً بسته شده است"
        )
    period.status = PeriodStatus.closed
    period.closed_at = datetime.now(UTC)
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="period_closed",
        new_value={"id": period.id, "name": period.name},
    )
    db.commit()
    db.refresh(period)
    return period


@router.get("/{period_id}/progress", response_model=PeriodProgress)
def period_progress(
    period_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> PeriodProgress:
    period = _get_period_or_404(db, period_id)

    # واجدان دوره: پرسنل فعالی که دسترسی ارزیابی برایشان تعریف شده است
    eligible_base = (
        select(Personnel)
        .join(EvaluationAccess, EvaluationAccess.personnel_id == Personnel.id)
        .where(Personnel.status == PersonnelStatus.active)
    )
    eligible = db.scalar(select(func.count()).select_from(eligible_base.subquery())) or 0

    started = (
        db.scalar(
            select(func.count())
            .select_from(EvaluationRecord)
            .where(EvaluationRecord.period_id == period_id)
        )
        or 0
    )
    finalized = (
        db.scalar(
            select(func.count())
            .select_from(EvaluationRecord)
            .where(
                EvaluationRecord.period_id == period_id,
                EvaluationRecord.status == EvaluationStatus.finalized,
            )
        )
        or 0
    )

    has_period_evaluation = (
        select(EvaluationRecord.id)
        .where(
            EvaluationRecord.subject_personnel_id == Personnel.id,
            EvaluationRecord.period_id == period_id,
        )
        .exists()
    )
    not_started_rows = db.execute(
        select(Personnel.id, Personnel.full_name, Personnel.org_unit)
        .join(EvaluationAccess, EvaluationAccess.personnel_id == Personnel.id)
        .where(Personnel.status == PersonnelStatus.active, ~has_period_evaluation)
        .order_by(Personnel.full_name)
    ).all()

    return PeriodProgress(
        period=PeriodRead.model_validate(period),
        eligible=eligible,
        started=started,
        finalized=finalized,
        not_started=[
            NotStartedPersonnel(personnel_id=pid, full_name=name, org_unit=unit)
            for pid, name, unit in not_started_rows
        ],
    )
