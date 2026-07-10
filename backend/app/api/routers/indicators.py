from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import IndicatorSection, UserRole
from app.models.evaluation import EvaluationScore
from app.models.indicator import Indicator
from app.schemas.auth import CurrentUser
from app.schemas.indicator import (
    IndicatorCreate,
    IndicatorRead,
    IndicatorReorder,
    IndicatorUpdate,
)
from app.services.audit import log_event

router = APIRouter(prefix="/api/indicators", tags=["indicators"])


@router.get("", response_model=list[IndicatorRead])
def list_indicators(
    section: IndicatorSection | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[Indicator]:
    query = select(Indicator)
    if section is not None:
        query = query.where(Indicator.section == section)
    if not include_inactive:
        query = query.where(Indicator.is_active.is_(True))
    query = query.order_by(Indicator.section, Indicator.display_order)
    return list(db.scalars(query))


@router.post("", response_model=IndicatorRead, status_code=status.HTTP_201_CREATED)
def create_indicator(
    payload: IndicatorCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> Indicator:
    # display_order به‌صورت خودکار به انتهای همان بخش اضافه می‌شود؛ ورودی کاربر نادیده
    # گرفته می‌شود تا HR مجبور به مدیریت دستی شماره‌ها نباشد (ترتیب با drag تغییر می‌کند).
    fields = payload.model_dump()
    max_order = db.scalar(
        select(func.max(Indicator.display_order)).where(Indicator.section == payload.section)
    )
    fields["display_order"] = (max_order or 0) + 1
    indicator = Indicator(**fields, is_active=True)
    db.add(indicator)
    db.flush()
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="indicator_created",
        new_value={
            "id": indicator.id,
            "section": indicator.section.value,
            "category": indicator.category,
            "description": indicator.description,
        },
    )
    db.commit()
    db.refresh(indicator)
    return indicator


@router.patch("/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_indicators(
    payload: IndicatorReorder,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> None:
    """ترتیب شاخص‌های یک بخش را بر اساس ترتیب drag کاربر بازنویسی می‌کند. ordered_ids
    باید دقیقاً همان مجموعهٔ شناسه‌های آن بخش باشد (نه کم، نه زیاد، بدون تکرار)."""
    existing = list(
        db.scalars(select(Indicator).where(Indicator.section == payload.section))
    )
    existing_ids = {ind.id for ind in existing}
    submitted_ids = set(payload.ordered_ids)
    if len(payload.ordered_ids) != len(submitted_ids) or submitted_ids != existing_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="فهرست ترتیب باید دقیقاً شامل همهٔ شاخص‌های همین بخش باشد",
        )

    by_id = {ind.id: ind for ind in existing}
    for position, indicator_id in enumerate(payload.ordered_ids, start=1):
        by_id[indicator_id].display_order = position

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="indicators_reordered",
        new_value={"section": payload.section.value, "ordered_ids": payload.ordered_ids},
    )
    db.commit()


@router.delete("/{indicator_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_indicator(
    indicator_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> None:
    """حذف کامل یک شاخص — فقط وقتی مجاز است که در هیچ ارزیابی‌ای امتیاز نخورده باشد؛
    در غیر این صورت داده‌های تاریخی می‌شکنند و باید به‌جای حذف، «غیرفعال» شود (۴۰۹)."""
    indicator = db.get(Indicator, indicator_id)
    if indicator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="شاخص یافت نشد")

    score_count = db.scalar(
        select(func.count())
        .select_from(EvaluationScore)
        .where(EvaluationScore.indicator_id == indicator_id)
    )
    if score_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "این شاخص در ارزیابی‌های ثبت‌شده استفاده شده و قابل حذف نیست؛ "
                "برای کنار گذاشتن آن از فرم‌های جدید، «غیرفعال»‌اش کنید."
            ),
        )

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="indicator_deleted",
        old_value={
            "id": indicator.id,
            "section": indicator.section.value,
            "category": indicator.category,
            "description": indicator.description,
        },
    )
    db.delete(indicator)
    db.commit()


@router.patch("/{indicator_id}", response_model=IndicatorRead)
def update_indicator(
    indicator_id: int,
    payload: IndicatorUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> Indicator:
    indicator = db.get(Indicator, indicator_id)
    if indicator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="شاخص یافت نشد")

    old_value = {
        "category": indicator.category,
        "description": indicator.description,
        "display_order": indicator.display_order,
        "is_active": indicator.is_active,
    }
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(indicator, field, value)

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="indicator_updated",
        old_value=old_value,
        new_value=updates,
    )
    db.commit()
    db.refresh(indicator)
    return indicator
