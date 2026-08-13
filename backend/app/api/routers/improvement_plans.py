"""مدیریت برنامه‌های بهبود (R13.2) — فقط منابع انسانی.

وقتی نتیجه یک ارزیابیِ نهایی‌شده «تمدید مشروط به برنامه بهبود مکتوب» است، HR می‌تواند
یک برنامه بهبود با اهداف مشخص، مسئول پیگیری و تاریخ بازنگری بسازد و آن را تا تکمیل
دنبال کند. زمان‌بند نزدیک‌شدن تاریخ بازنگری را یادآوری می‌کند (services/scheduled).
"""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_roles
from app.core.constants import CONDITIONAL_RENEWAL_RECOMMENDATION
from app.db.session import get_db
from app.models.enums import EvaluationStatus, ImprovementPlanStatus, UserRole
from app.models.evaluation import EvaluationRecord
from app.models.improvement_plan import ImprovementPlan, ImprovementPlanGoal
from app.models.personnel import Personnel
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.schemas.improvement_plan import (
    EligibleEvaluation,
    GoalCreate,
    GoalRead,
    GoalUpdate,
    ImprovementPlanCreate,
    ImprovementPlanDetail,
    ImprovementPlanPage,
    ImprovementPlanRead,
    ImprovementPlanUpdate,
)
from app.services.audit import log_event
from app.services.excel import build_improvement_plans_workbook
from app.services.notifications import notify

router = APIRouter(prefix="/api/improvement-plans", tags=["improvement-plans"])


def _get_plan_or_404(db: Session, plan_id: int) -> ImprovementPlan:
    plan = db.get(ImprovementPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="برنامه بهبود یافت نشد")
    return plan


def _ensure_plan_open(plan: ImprovementPlan) -> None:
    """اهداف فقط روی برنامهٔ باز قابل افزودن/ویرایش/حذف‌اند؛ برنامهٔ تکمیل/لغوشده
    یک سند بسته است و نباید پس از بسته‌شدن تغییر کند."""
    if plan.status != ImprovementPlanStatus.open:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="این برنامه دیگر باز نیست؛ امکان تغییر اهداف وجود ندارد",
        )


def _ensure_owner_is_valid(db: Session, owner_user_id: int | None) -> None:
    if owner_user_id is None:
        return
    owner = db.get(User, owner_user_id)
    if owner is None or not owner.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="کاربر مسئول پیگیری یافت نشد یا غیرفعال است",
        )


@router.get("/eligible", response_model=list[EligibleEvaluation])
def list_eligible_evaluations(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> list[EligibleEvaluation]:
    """ارزیابی‌های نهایی‌شده با نتیجه «تمدید مشروط» که هنوز برنامه بهبود ندارند."""
    has_plan = select(ImprovementPlan.id).where(
        ImprovementPlan.evaluation_record_id == EvaluationRecord.id
    ).exists()
    rows = db.scalars(
        select(EvaluationRecord)
        .where(
            EvaluationRecord.status == EvaluationStatus.finalized,
            EvaluationRecord.recommendation == CONDITIONAL_RENEWAL_RECOMMENDATION,
            ~has_plan,
        )
        .order_by(EvaluationRecord.finalized_at.desc())
    )
    return [
        EligibleEvaluation(
            evaluation_record_id=r.id,
            evaluation_code=r.evaluation_code,
            personnel_id=r.subject_personnel_id,
            personnel_full_name=r.subject.full_name,
            final_weighted_pct=r.final_weighted_pct,
            finalized_at=r.finalized_at,
        )
        for r in rows
    ]


@router.get("", response_model=ImprovementPlanPage)
def list_plans(
    status_filter: ImprovementPlanStatus | None = Query(default=None, alias="status"),
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> ImprovementPlanPage:
    query = select(ImprovementPlan)
    if status_filter is not None:
        query = query.where(ImprovementPlan.status == status_filter)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.join(Personnel, Personnel.id == ImprovementPlan.personnel_id).where(
            Personnel.full_name.ilike(pattern) | ImprovementPlan.title.ilike(pattern)
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(
        db.scalars(query.order_by(ImprovementPlan.review_date).limit(limit).offset(offset))
    )
    return ImprovementPlanPage(
        total=total, items=[ImprovementPlanRead.model_validate(p) for p in items]
    )


@router.post("", response_model=ImprovementPlanDetail, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: ImprovementPlanCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> ImprovementPlan:
    record = db.get(EvaluationRecord, payload.evaluation_record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ارزیابی یافت نشد")
    if record.status != EvaluationStatus.finalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برنامه بهبود فقط برای ارزیابی نهایی‌شده قابل تعریف است",
        )
    if record.recommendation != CONDITIONAL_RENEWAL_RECOMMENDATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برنامه بهبود فقط برای نتیجه «تمدید مشروط به برنامه بهبود مکتوب» معنا دارد",
        )
    _ensure_owner_is_valid(db, payload.owner_user_id)

    plan = ImprovementPlan(
        evaluation_record_id=record.id,
        personnel_id=record.subject_personnel_id,
        title=payload.title,
        owner_user_id=payload.owner_user_id,
        status=ImprovementPlanStatus.open,
        review_date=payload.review_date,
        summary=payload.summary,
        created_by_user_id=current_user.id,
    )
    for order, description in enumerate(payload.goals):
        text = description.strip()
        if text:
            plan.goals.append(ImprovementPlanGoal(description=text, display_order=order))
    db.add(plan)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="برای این ارزیابی قبلاً یک برنامه بهبود ثبت شده است",
        ) from exc

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="improvement_plan_created",
        evaluation_record_id=record.id,
        new_value={"plan_id": plan.id, "title": plan.title},
    )
    if plan.owner_user_id is not None:
        notify(
            db,
            [plan.owner_user_id],
            type_="improvement_plan_assigned",
            message=(
                f"برنامه بهبود «{plan.title}» برای {record.subject.full_name} "
                "به شما به‌عنوان مسئول پیگیری سپرده شد"
            ),
            evaluation_record_id=record.id,
            link=f"/hr/improvement-plans/{plan.id}",
        )
    db.commit()
    db.refresh(plan)
    return plan


# مسیر ثابت پیش از "/{plan_id}" تا "export.xlsx" شناسهٔ عددی تفسیر نشود
@router.get("/export.xlsx")
def export_plans_excel(
    status_filter: ImprovementPlanStatus | None = Query(default=None, alias="status"),
    q: str | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> Response:
    """خروجی Excel از برنامه‌های بهبود (فقط HR) با همان فیلترهای فهرست."""
    query = select(ImprovementPlan).options(selectinload(ImprovementPlan.goals))
    if status_filter is not None:
        query = query.where(ImprovementPlan.status == status_filter)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.join(Personnel, Personnel.id == ImprovementPlan.personnel_id).where(
            Personnel.full_name.ilike(pattern) | ImprovementPlan.title.ilike(pattern)
        )
    plans = list(db.scalars(query.order_by(ImprovementPlan.review_date)))

    # دو کوئری دسته‌ای به‌جای N+1: کد ارزیابی و نام مسئول پیگیری هر برنامه
    evaluation_ids = {p.evaluation_record_id for p in plans}
    evaluation_codes = (
        dict(
            db.execute(
                select(EvaluationRecord.id, EvaluationRecord.evaluation_code).where(
                    EvaluationRecord.id.in_(evaluation_ids)
                )
            ).all()
        )
        if evaluation_ids
        else {}
    )
    owner_ids = {p.owner_user_id for p in plans if p.owner_user_id is not None}
    owner_usernames = (
        dict(db.execute(select(User.id, User.username).where(User.id.in_(owner_ids))).all())
        if owner_ids
        else {}
    )

    log_event(db, actor_user_id=current_user.id, event_type="improvement_plans_excel_exported")
    db.commit()
    return Response(
        content=build_improvement_plans_workbook(plans, evaluation_codes, owner_usernames),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="improvement-plans.xlsx"'},
    )


@router.get("/{plan_id}", response_model=ImprovementPlanDetail)
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> ImprovementPlan:
    return _get_plan_or_404(db, plan_id)


@router.patch("/{plan_id}", response_model=ImprovementPlanDetail)
def update_plan(
    plan_id: int,
    payload: ImprovementPlanUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> ImprovementPlan:
    plan = _get_plan_or_404(db, plan_id)
    updates = payload.model_dump(exclude_unset=True)

    previous_owner_id = plan.owner_user_id
    if "owner_user_id" in updates:
        _ensure_owner_is_valid(db, updates["owner_user_id"])
    if updates.get("follow_up_evaluation_id") is not None:
        follow_up = db.get(EvaluationRecord, updates["follow_up_evaluation_id"])
        if follow_up is None or follow_up.subject_personnel_id != plan.personnel_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ارزیابی پیگیری باید متعلق به همان پرسنل باشد",
            )

    for field, value in updates.items():
        setattr(plan, field, value)

    # سپردن (یا تغییر) مسئول پیگیری، مسئول جدید را باخبر می‌کند
    if plan.owner_user_id is not None and plan.owner_user_id != previous_owner_id:
        notify(
            db,
            [plan.owner_user_id],
            type_="improvement_plan_assigned",
            message=(
                f"برنامه بهبود «{plan.title}» برای {plan.personnel.full_name} "
                "به شما به‌عنوان مسئول پیگیری سپرده شد"
            ),
            evaluation_record_id=plan.evaluation_record_id,
            link=f"/hr/improvement-plans/{plan.id}",
        )
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="improvement_plan_updated",
        evaluation_record_id=plan.evaluation_record_id,
        new_value={"plan_id": plan.id, "fields": sorted(updates.keys())},
    )
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/{plan_id}/complete", response_model=ImprovementPlanDetail)
def complete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> ImprovementPlan:
    plan = _get_plan_or_404(db, plan_id)
    if plan.status != ImprovementPlanStatus.open:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="این برنامه دیگر باز نیست"
        )
    plan.status = ImprovementPlanStatus.completed
    plan.completed_at = datetime.now(UTC)
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="improvement_plan_completed",
        evaluation_record_id=plan.evaluation_record_id,
        new_value={"plan_id": plan.id},
    )
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/{plan_id}/cancel", response_model=ImprovementPlanDetail)
def cancel_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> ImprovementPlan:
    plan = _get_plan_or_404(db, plan_id)
    if plan.status != ImprovementPlanStatus.open:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="این برنامه دیگر باز نیست"
        )
    plan.status = ImprovementPlanStatus.cancelled
    plan.completed_at = datetime.now(UTC)
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="improvement_plan_cancelled",
        evaluation_record_id=plan.evaluation_record_id,
        new_value={"plan_id": plan.id},
    )
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/{plan_id}/goals", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
def add_goal(
    plan_id: int,
    payload: GoalCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> ImprovementPlanGoal:
    plan = _get_plan_or_404(db, plan_id)
    _ensure_plan_open(plan)
    next_order = (
        db.scalar(
            select(func.coalesce(func.max(ImprovementPlanGoal.display_order), -1)).where(
                ImprovementPlanGoal.plan_id == plan.id
            )
        )
        + 1
    )
    goal = ImprovementPlanGoal(
        plan_id=plan.id, description=payload.description, display_order=next_order
    )
    db.add(goal)
    db.flush()
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="improvement_goal_added",
        evaluation_record_id=plan.evaluation_record_id,
        new_value={"plan_id": plan.id, "goal_id": goal.id, "description": goal.description},
    )
    db.commit()
    db.refresh(goal)
    return goal


@router.patch("/{plan_id}/goals/{goal_id}", response_model=GoalRead)
def update_goal(
    plan_id: int,
    goal_id: int,
    payload: GoalUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> ImprovementPlanGoal:
    goal = db.get(ImprovementPlanGoal, goal_id)
    if goal is None or goal.plan_id != plan_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="هدف یافت نشد")
    plan = _get_plan_or_404(db, plan_id)
    _ensure_plan_open(plan)
    updates = payload.model_dump(exclude_unset=True)
    before = {"description": goal.description, "is_done": goal.is_done}
    for field, value in updates.items():
        setattr(goal, field, value)
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="improvement_goal_updated",
        evaluation_record_id=plan.evaluation_record_id,
        old_value=before,
        new_value={"plan_id": plan.id, "goal_id": goal.id, **updates},
    )
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/{plan_id}/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    plan_id: int,
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> None:
    goal = db.get(ImprovementPlanGoal, goal_id)
    if goal is None or goal.plan_id != plan_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="هدف یافت نشد")
    plan = _get_plan_or_404(db, plan_id)
    _ensure_plan_open(plan)
    # مقدار پیشین پیش از حذف ثبت می‌شود، وگرنه از هدفِ حذف‌شده هیچ نمی‌ماند
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="improvement_goal_deleted",
        evaluation_record_id=plan.evaluation_record_id,
        old_value={
            "plan_id": plan.id,
            "goal_id": goal.id,
            "description": goal.description,
            "is_done": goal.is_done,
        },
    )
    db.delete(goal)
    db.commit()
