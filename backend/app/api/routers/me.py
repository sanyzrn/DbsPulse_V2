"""«کارنامه من»: نمای شخصی کارمند از نتایج نهایی ارزیابی خودش + رؤیت رسمی.

کارمند (نقش employee) به پرونده کامل دسترسی ندارد — شواهد و کامنت‌های داخلی
زنجیره تأیید خصوصی می‌مانند؛ فقط خلاصه نتیجه نهایی‌شده را می‌بیند و با «رؤیت شد»
به‌صورت رسمی و قابل‌استناد (audit) تأیید می‌کند که نتیجه به او ابلاغ شده است.
"""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.enums import EvaluationStatus, ImprovementPlanStatus, UserRole
from app.models.evaluation import EvaluationRecord
from app.models.improvement_plan import ImprovementPlan
from app.schemas.auth import CurrentUser
from app.schemas.evaluation import MyEvaluationPage, MyEvaluationRead
from app.schemas.improvement_plan import ImprovementPlanDetail
from app.services.audit import log_event
from app.services.notifications import notify

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("/evaluations", response_model=MyEvaluationPage)
def my_evaluations(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.employee)),
) -> MyEvaluationPage:
    if current_user.personnel_id is None:
        return MyEvaluationPage(total=0, items=[])
    query = select(EvaluationRecord).where(
        EvaluationRecord.subject_personnel_id == current_user.personnel_id,
        EvaluationRecord.status == EvaluationStatus.finalized,
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.order_by(EvaluationRecord.finalized_at.desc())))
    return MyEvaluationPage(
        total=total, items=[MyEvaluationRead.model_validate(r) for r in items]
    )


@router.get("/improvement-plans", response_model=list[ImprovementPlanDetail])
def my_improvement_plans(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.employee)),
) -> list[ImprovementPlan]:
    """برنامه‌های بهبودِ بازِ خود کارمند (فقط خواندنی) — تا بداند چه انتظاری از او می‌رود."""
    if current_user.personnel_id is None:
        return []
    return list(
        db.scalars(
            select(ImprovementPlan)
            .where(
                ImprovementPlan.personnel_id == current_user.personnel_id,
                ImprovementPlan.status == ImprovementPlanStatus.open,
            )
            .order_by(ImprovementPlan.review_date)
        )
    )


@router.post("/evaluations/{evaluation_id}/acknowledge", response_model=MyEvaluationRead)
def acknowledge_evaluation(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.employee)),
) -> EvaluationRecord:
    record = db.get(EvaluationRecord, evaluation_id)
    # پرونده دیگران عمداً 404 برمی‌گردد (نه 403) تا وجودش هم لو نرود
    if (
        record is None
        or current_user.personnel_id is None
        or record.subject_personnel_id != current_user.personnel_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ارزیابی یافت نشد")
    if record.status != EvaluationStatus.finalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="فقط ارزیابی نهایی‌شده قابل رؤیت است",
        )
    if record.acknowledged_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این ارزیابی قبلاً رؤیت شده است",
        )

    record.acknowledged_at = datetime.now(UTC)
    record.acknowledged_by_user_id = current_user.id
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="evaluation_acknowledged",
        evaluation_record_id=record.id,
        new_value={"acknowledged_at": record.acknowledged_at.isoformat()},
    )

    from app.models.user import User

    hr_ids = list(
        db.scalars(
            select(User.id).where(User.role == UserRole.hr, User.is_active.is_(True))
        )
    )
    notify(
        db,
        hr_ids,
        type_="evaluation_acknowledged",
        message=(
            f"کارمند {record.subject.full_name} نتیجه پرونده "
            f"{record.evaluation_code} را رؤیت کرد"
        ),
        evaluation_record_id=record.id,
        link=f"/evaluations/{record.id}",
    )

    db.commit()
    db.refresh(record)
    return record
