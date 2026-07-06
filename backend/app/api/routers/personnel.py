from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import EvaluationStatus, UserRole
from app.models.evaluation import EvaluationRecord
from app.models.evaluation_access import EvaluationAccess
from app.models.personnel import Personnel
from app.schemas.auth import CurrentUser
from app.schemas.personnel import PersonnelCreate, PersonnelPage, PersonnelRead, PersonnelUpdate
from app.services.audit import log_event

router = APIRouter(prefix="/api/personnel", tags=["personnel"])

_ACCESS_COLUMN_BY_ROLE = {
    UserRole.unit_supervisor: EvaluationAccess.unit_supervisor_user_id,
    UserRole.deputy: EvaluationAccess.deputy_user_id,
    UserRole.ceo: EvaluationAccess.ceo_user_id,
}


def _can_view_personnel(db: Session, personnel_id: int, current_user: CurrentUser) -> bool:
    if current_user.role == UserRole.hr:
        return True
    access = db.scalar(
        select(EvaluationAccess).where(EvaluationAccess.personnel_id == personnel_id)
    )
    if access is not None and current_user.id in {
        access.unit_supervisor_user_id,
        access.deputy_user_id,
        access.ceo_user_id,
    }:
        return True
    involved_record = db.scalar(
        select(EvaluationRecord).where(
            EvaluationRecord.subject_personnel_id == personnel_id,
            (EvaluationRecord.unit_supervisor_user_id == current_user.id)
            | (EvaluationRecord.deputy_user_id == current_user.id)
            | (EvaluationRecord.ceo_user_id == current_user.id),
        )
    )
    return involved_record is not None


@router.get("", response_model=PersonnelPage)
def list_personnel(
    accessible_to_me: bool = False,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PersonnelPage:
    query = select(Personnel)
    # نقش‌های غیر از HR فقط پرسنلی را می‌بینند که برایشان دسترسی ارزیابی تعریف شده؛
    # HR به کل فهرست پرسنل دسترسی دارد (طبق بخش ۴ سند مشخصات).
    if current_user.role != UserRole.hr or accessible_to_me:
        column = _ACCESS_COLUMN_BY_ROLE.get(current_user.role)
        if column is None:
            return PersonnelPage(total=0, items=[])
        query = query.join(EvaluationAccess, EvaluationAccess.personnel_id == Personnel.id).where(
            column == current_user.id
        )
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            Personnel.full_name.ilike(pattern)
            | Personnel.personnel_code.ilike(pattern)
            | Personnel.job_title.ilike(pattern)
            | Personnel.org_unit.ilike(pattern)
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.order_by(Personnel.full_name).limit(limit).offset(offset)))
    return PersonnelPage(total=total, items=[PersonnelRead.model_validate(p) for p in items])


@router.post("", response_model=PersonnelRead, status_code=status.HTTP_201_CREATED)
def create_personnel(
    payload: PersonnelCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> Personnel:
    existing = db.scalar(select(Personnel).where(Personnel.personnel_code == payload.personnel_code))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="کد پرسنلی تکراری است"
        )
    personnel = Personnel(**payload.model_dump(), created_by_user_id=current_user.id)
    db.add(personnel)
    db.flush()
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="personnel_created",
        new_value={
            "id": personnel.id,
            "personnel_code": personnel.personnel_code,
            "full_name": personnel.full_name,
        },
    )
    db.commit()
    db.refresh(personnel)
    return personnel


@router.get("/{personnel_id}", response_model=PersonnelRead)
def get_personnel(
    personnel_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Personnel:
    personnel = db.get(Personnel, personnel_id)
    if personnel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    if not _can_view_personnel(db, personnel_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="شما به این پرسنل دسترسی ندارید"
        )
    return personnel


@router.patch("/{personnel_id}", response_model=PersonnelRead)
def update_personnel(
    personnel_id: int,
    payload: PersonnelUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> Personnel:
    personnel = db.get(Personnel, personnel_id)
    if personnel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")

    updates = payload.model_dump(exclude_unset=True)
    if "personnel_code" in updates and updates["personnel_code"] != personnel.personnel_code:
        existing = db.scalar(
            select(Personnel).where(Personnel.personnel_code == updates["personnel_code"])
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="کد پرسنلی تکراری است"
            )

    # تغییر is_manager یک متغیر ساختاری گردش‌کار است (وجود/عدم‌وجود مرحلهٔ مسئول
    # واحد). اگر ارزیابی بازی (نهایی‌نشده) روی همین فرد در جریان باشد، آن رکورد
    # دیگر با انتظارات مسیر جدید هماهنگ نیست؛ به‌جای رفتار نامشخص، تغییر را مسدود
    # می‌کنیم تا HR اول تکلیف ارزیابی باز را روشن کند.
    if "is_manager" in updates and updates["is_manager"] != personnel.is_manager:
        open_evaluation = db.scalar(
            select(EvaluationRecord).where(
                EvaluationRecord.subject_personnel_id == personnel.id,
                EvaluationRecord.status != EvaluationStatus.finalized,
            )
        )
        if open_evaluation is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "این پرسنل ارزیابی باز (نهایی‌نشده) دارد؛ ابتدا آن را نهایی یا "
                    "لغو کنید و سپس وضعیت «مدیر» را تغییر دهید"
                ),
            )

    def _jsonable(value: object) -> object:
        return value.value if hasattr(value, "value") else str(value)

    old_value = {field: _jsonable(getattr(personnel, field)) for field in updates}
    for field, value in updates.items():
        setattr(personnel, field, value)

    # بررسی ترتیب تاریخ‌ها بعد از اعمال تغییرات، تا آپدیت جزئی (فقط یک تاریخ) هم پوشش داده شود
    if personnel.contract_end_date <= personnel.contract_start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ پایان قرارداد باید بعد از تاریخ شروع قرارداد باشد",
        )

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="personnel_updated",
        old_value=old_value,
        new_value={"id": personnel.id, **payload.model_dump(exclude_unset=True, mode="json")},
    )

    # اگر فرد به «مدیر» تبدیل شود، دسترسی مسئول واحد قبلی (در صورت وجود) دیگر معتبر
    # نیست؛ طبق همان قانونی که در ثبت/ویرایش دسترسی اعمال می‌شود، باید خودکار پاک شود.
    if personnel.is_manager:
        access = db.scalar(
            select(EvaluationAccess).where(EvaluationAccess.personnel_id == personnel.id)
        )
        if access is not None and access.unit_supervisor_user_id is not None:
            old_supervisor_id = access.unit_supervisor_user_id
            access.unit_supervisor_user_id = None
            access.updated_by_user_id = current_user.id
            log_event(
                db,
                actor_user_id=current_user.id,
                event_type="access_supervisor_cleared_on_manager_title",
                old_value={"unit_supervisor_user_id": old_supervisor_id},
                new_value={"unit_supervisor_user_id": None, "personnel_id": personnel.id},
            )

    db.commit()
    db.refresh(personnel)
    return personnel
