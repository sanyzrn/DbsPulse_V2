"""مدیریت سامانه: مجوزها و ماژول‌ها (نیمهٔ دوم P0-03).

این روتر عمداً از `personnel` و `evaluations` جداست: کارهای این‌جا دربارهٔ *خودِ
سامانه* است، نه دربارهٔ ارزیابی کسی. همان تفکیکی که کل این تغییر برای آن انجام
شده — کسی که سامانه را نگه می‌دارد لازم نیست نمرهٔ کسی را ببیند.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_capability
from app.core.modules import MODULES, MODULES_BY_KEY
from app.db.session import get_db
from app.models.capability import UserCapability
from app.models.enums import Capability, UserRole
from app.models.module import ModuleSetting
from app.models.user import User
from app.schemas.administration import (
    CapabilityGrant,
    CapabilityHolder,
    ModuleState,
    ModuleToggle,
    MyPermissions,
)
from app.schemas.auth import CurrentUser
from app.services.audit import log_event
from app.services.authorization import capabilities_of, module_states

router = APIRouter(prefix="/api/administration", tags=["administration"])

#: توضیح فارسیِ هر مجوز — یک‌جا، تا UI و پیام‌های خطا یک زبان داشته باشند.
CAPABILITY_LABELS: dict[Capability, str] = {
    Capability.manage_users: "مدیریت کاربران و مجوزها",
    Capability.manage_scoring: "شاخص‌ها و طرح نمره‌دهی",
    Capability.manage_integrations: "تنظیمات ایمیل و پیامک",
    Capability.manage_modules: "روشن و خاموش کردن بخش‌ها",
    Capability.view_diagnostics: "سلامت سامانه و صف تحویل",
}


@router.get("/my-permissions", response_model=MyPermissions)
def my_permissions(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> MyPermissions:
    """مجوزهای خودِ کاربر و وضعیت ماژول‌ها — برای اینکه فرانت‌اند بداند چه چیزی
    را اصلاً نشان بدهد.

    بدون این، منو گزینه‌هایی نشان می‌داد که کلیکشان ۴۰۳ می‌گیرد. گزینه‌ای که
    اجازه‌اش را نداری، بهتر است اصلاً نباشد تا اینکه باشد و رد شود.
    """
    return MyPermissions(
        capabilities=sorted(c.value for c in capabilities_of(db, current_user.id)),
        modules=module_states(db),
    )


@router.get("/capabilities", response_model=list[CapabilityHolder])
def list_capability_holders(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_users)),
) -> list[CapabilityHolder]:
    """چه کسی چه اختیاری دارد.

    کارمندان عادی عمداً این‌جا نیستند: فهرست باید *کوتاه و قابل مرور* بماند تا
    کسی که دنبال «چه کسی می‌تواند قواعد را عوض کند» می‌گردد، جوابش را ببیند نه
    اینکه در دویست ردیف دنبالش بگردد.
    """
    users = db.scalars(
        select(User)
        .where(User.role != UserRole.employee)
        .order_by(User.role, User.username)
    ).all()
    held: dict[int, set[Capability]] = {}
    for row in db.scalars(select(UserCapability)):
        held.setdefault(row.user_id, set()).add(row.capability)

    return [
        CapabilityHolder(
            user_id=user.id,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            capabilities=sorted(c.value for c in held.get(user.id, set())),
        )
        for user in users
    ]


@router.put("/capabilities/{user_id}", response_model=CapabilityHolder)
def set_capabilities(
    user_id: int,
    payload: CapabilityGrant,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_users)),
) -> CapabilityHolder:
    """مجموعهٔ کامل مجوزهای یک کاربر را جایگزین می‌کند."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="کاربر یافت نشد")
    if user.role is UserRole.employee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="کارمند عادی مجوز اداری نمی‌گیرد؛ اگر لازم است، نقشش را عوض کنید",
        )

    desired = {Capability(value) for value in payload.capabilities}
    current = capabilities_of(db, user_id)

    # آخرین دارندهٔ manage_users نمی‌تواند آن را از خودش بگیرد.
    #
    # بدون این گارد، یک کلیک اشتباه سامانه را در حالتی قفل می‌کند که هیچ‌کس
    # نمی‌تواند به کسی مجوز بدهد — و تنها راه خروج، SQL دستی روی پروداکشن است.
    if Capability.manage_users in current and Capability.manage_users not in desired:
        others = db.scalar(
            select(User.id)
            .join(UserCapability, UserCapability.user_id == User.id)
            .where(
                UserCapability.capability == Capability.manage_users,
                User.id != user_id,
                User.is_active.is_(True),
            )
            .limit(1)
        )
        if others is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "این تنها حساب فعالی است که می‌تواند مجوز بدهد؛ ابتدا این مجوز را "
                    "به کاربر دیگری بدهید، بعد از این یکی بگیرید"
                ),
            )

    for capability in current - desired:
        db.query(UserCapability).filter(
            UserCapability.user_id == user_id, UserCapability.capability == capability
        ).delete()
    for capability in desired - current:
        db.add(
            UserCapability(
                user_id=user_id, capability=capability, granted_by_user_id=current_user.id
            )
        )

    # چه کسی به چه کسی چه اختیاری داد — دقیقاً همان چیزی که این تفکیک برایش است
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="capabilities_changed",
        old_value={"user": user.username, "capabilities": sorted(c.value for c in current)},
        new_value={"user": user.username, "capabilities": sorted(c.value for c in desired)},
    )
    db.commit()

    return CapabilityHolder(
        user_id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        capabilities=sorted(c.value for c in desired),
    )


@router.get("/modules", response_model=list[ModuleState])
def list_modules(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_modules)),
) -> list[ModuleState]:
    states = module_states(db)
    return [
        ModuleState(
            key=module.key,
            label=module.label,
            description=module.description,
            enabled=states[module.key],
        )
        for module in MODULES
    ]


@router.put("/modules/{key}", response_model=ModuleState)
def toggle_module(
    key: str,
    payload: ModuleToggle,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_modules)),
) -> ModuleState:
    """روشن یا خاموش کردن یک بخش.

    خاموش‌کردن هیچ داده‌ای را حذف نمی‌کند: فقط ورودی‌های نوشتن بسته و بخش از منو
    برداشته می‌شود. آنچه ثبت شده سر جایش می‌ماند و با روشن‌کردن دوباره برمی‌گردد.
    """
    module = MODULES_BY_KEY.get(key)
    if module is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="چنین بخشی وجود ندارد")

    row = db.get(ModuleSetting, key)
    was = row.enabled if row is not None else module.default_enabled
    if row is None:
        row = ModuleSetting(key=key, enabled=payload.enabled)
        db.add(row)
    else:
        row.enabled = payload.enabled
    row.updated_by_user_id = current_user.id

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="module_toggled",
        old_value={"module": key, "enabled": was},
        new_value={"module": key, "enabled": payload.enabled},
    )
    db.commit()

    return ModuleState(
        key=module.key,
        label=module.label,
        description=module.description,
        enabled=payload.enabled,
    )
