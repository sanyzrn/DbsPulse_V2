from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import IndicatorSection, UserRole
from app.models.indicator import Indicator
from app.schemas.auth import CurrentUser
from app.schemas.indicator import IndicatorCreate, IndicatorRead, IndicatorUpdate
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
    indicator = Indicator(**payload.model_dump(), is_active=True)
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
