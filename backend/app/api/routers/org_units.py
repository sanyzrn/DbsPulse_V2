"""تعریف واحدهای سازمانی.

تا امروز فهرست واحدها از خودِ داده استخراج می‌شد: هر واحدی که کسی در آن ثبت شده
بود. یعنی غلط تایپی یک واحد تازه می‌ساخت، و واحدی که هنوز کسی در آن نبود اصلاً
وجود نداشت.

این‌جا فهرست *تعریف* می‌شود. `personnel.org_unit` همچنان رشته می‌ماند — این
کاتالوگ فقط می‌گوید چه چیزی در فرم پیشنهاد شود و چه چیزی در فیلترها بیاید.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_role_or_capability
from app.db.session import get_db
from app.models.enums import Capability, UserRole
from app.models.org_unit import OrgUnit
from app.models.personnel import Personnel
from app.schemas.auth import CurrentUser
from app.schemas.org_unit import OrgUnitCreate, OrgUnitRead, OrgUnitUpdate
from app.services.audit import log_event

router = APIRouter(prefix="/api/org-units", tags=["org-units"])

_guard = require_role_or_capability(UserRole.hr, Capability.manage_personnel)


def _to_read(db: Session, units: list[OrgUnit]) -> list[OrgUnitRead]:
    """با تعدادِ پرسنلِ هر واحد.

    بدون این عدد، «حذف» یک تصمیمِ کور است: کسی که واحدی را برمی‌دارد نمی‌داند
    دوازده نفر در آن هستند یا هیچ‌کس.
    """
    counts = dict(
        db.execute(
            select(Personnel.org_unit, func.count()).group_by(Personnel.org_unit)
        ).all()
    )
    return [
        OrgUnitRead(
            id=unit.id,
            site=unit.site,
            name=unit.name,
            full_name=unit.full_name,
            is_active=unit.is_active,
            display_order=unit.display_order,
            personnel_count=counts.get(unit.full_name, 0),
        )
        for unit in units
    ]


@router.get("", response_model=list[OrgUnitRead])
def list_org_units(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(_guard),
) -> list[OrgUnitRead]:
    units = list(
        db.scalars(select(OrgUnit).order_by(OrgUnit.display_order, OrgUnit.site, OrgUnit.name))
    )
    return _to_read(db, units)


@router.post("", response_model=OrgUnitRead, status_code=status.HTTP_201_CREATED)
def create_org_unit(
    payload: OrgUnitCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(_guard),
) -> OrgUnitRead:
    unit = OrgUnit(
        site=(payload.site or "").strip() or None,
        name=payload.name.strip(),
        is_active=True,
        display_order=db.scalar(select(func.coalesce(func.max(OrgUnit.display_order), 0))) + 1,
    )
    db.add(unit)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این واحد در همین محل از قبل تعریف شده است",
        ) from None

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="org_unit_created",
        new_value={"id": unit.id, "full_name": unit.full_name},
    )
    db.commit()
    db.refresh(unit)
    return _to_read(db, [unit])[0]


@router.patch("/{unit_id}", response_model=OrgUnitRead)
def update_org_unit(
    unit_id: int,
    payload: OrgUnitUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(_guard),
) -> OrgUnitRead:
    """تغییر نام واحد — و همراهش، پرسنلِ همان واحد.

    اگر فقط کاتالوگ عوض می‌شد، پرسنلِ موجود روی نام قدیمی می‌ماندند و سامانه دو
    واحد نشان می‌داد: یکی در کاتالوگ و یکی در داده. تغییرِ نام یک *اصلاح* است،
    نه ساختن یک واحد تازه — پس هر دو با هم عوض می‌شوند.
    """
    unit = db.get(OrgUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="واحد یافت نشد")

    updates = payload.model_dump(exclude_unset=True)
    old_full_name = unit.full_name
    if "site" in updates:
        unit.site = (updates["site"] or "").strip() or None
    if "name" in updates:
        unit.name = updates["name"].strip()
    if "is_active" in updates:
        unit.is_active = updates["is_active"]

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این واحد در همین محل از قبل تعریف شده است",
        ) from None

    moved = 0
    if unit.full_name != old_full_name:
        moved = (
            db.query(Personnel)
            .filter(Personnel.org_unit == old_full_name)
            .update({Personnel.org_unit: unit.full_name}, synchronize_session=False)
        )

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="org_unit_updated",
        old_value={"full_name": old_full_name},
        new_value={"id": unit.id, "full_name": unit.full_name, "personnel_moved": moved},
    )
    db.commit()
    db.refresh(unit)
    return _to_read(db, [unit])[0]


@router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_org_unit(
    unit_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(_guard),
):
    """حذف فقط برای واحدِ خالی.

    واحدی که پرسنل دارد حذف نمی‌شود، چون حذفش نه آن پرسنل را جابه‌جا می‌کند و نه
    گزارش‌های گذشته را — فقط فهرست را با واقعیت ناهماهنگ می‌کند. برای واحدی که
    دیگر استفاده نمی‌شود ولی سابقه دارد، «غیرفعال» درست است: از فرمِ ثبت
    برداشته می‌شود و در گزارش‌ها می‌ماند.
    """
    unit = db.get(OrgUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="واحد یافت نشد")

    in_use = db.scalar(
        select(func.count()).select_from(Personnel).where(Personnel.org_unit == unit.full_name)
    )
    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"{in_use} نفر در این واحد ثبت شده‌اند. برای کنار گذاشتنش از فرم‌های تازه، "
                "«غیرفعال»‌اش کنید — این‌طور سابقهٔ گزارش‌ها هم دست‌نخورده می‌ماند."
            ),
        )

    snapshot = {"id": unit.id, "full_name": unit.full_name}
    db.delete(unit)
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="org_unit_deleted",
        old_value=snapshot,
    )
    db.commit()
    return None



