from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_capability
from app.core.security import hash_password
from app.db.session import get_db
from app.models.enums import Capability, UserRole
from app.models.personnel import Personnel
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.schemas.user import UserCreate, UserPage, UserRead, UserUpdate
from app.services.audit import log_event
from app.services.excel import build_users_workbook
from app.services.self_evaluation import ensure_user_link_is_not_self_evaluation
from app.services.sessions import revoke_all_for_user

router = APIRouter(prefix="/api/users", tags=["users"])


def _apply_user_filters(query, *, role: UserRole | None, q: str | None, is_active: bool | None):
    if role is not None:
        query = query.where(User.role == role)
    if q:
        query = query.where(User.username.ilike(f"%{q.strip()}%"))
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    return query


@router.get("", response_model=UserPage)
def list_users(
    role: UserRole | None = None,
    q: str | None = None,
    is_active: bool | None = None,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_users)),
) -> UserPage:
    query = _apply_user_filters(select(User), role=role, q=q, is_active=is_active)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.order_by(User.username).limit(limit).offset(offset)))
    return UserPage(total=total, items=[UserRead.model_validate(u) for u in items])


@router.get("/export.xlsx")
def export_users_excel(
    role: UserRole | None = None,
    q: str | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_users)),
) -> Response:
    """خروجی Excel از فهرست کاربران (فقط HR) با همان فیلترهای فهرست."""
    query = _apply_user_filters(select(User), role=role, q=q, is_active=is_active)
    users = list(db.scalars(query.order_by(User.username)))
    # نام پرسنل مرتبط با یک کوئری دسته‌ای (نه N+1)
    personnel_ids = {u.personnel_id for u in users if u.personnel_id is not None}
    personnel_names = (
        dict(
            db.execute(
                select(Personnel.id, Personnel.full_name).where(Personnel.id.in_(personnel_ids))
            ).all()
        )
        if personnel_ids
        else {}
    )
    log_event(db, actor_user_id=current_user.id, event_type="users_excel_exported")
    db.commit()
    return Response(
        content=build_users_workbook(users, personnel_names),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="users.xlsx"'},
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_users)),
) -> User:
    existing = db.scalar(select(User).where(User.username == payload.username))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="نام کاربری تکراری است"
        )
    if payload.personnel_id is not None and db.get(Personnel, payload.personnel_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="پرسنل انتخاب‌شده یافت نشد"
        )
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        personnel_id=payload.personnel_id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="user_created",
        new_value={"id": user.id, "username": user.username, "role": user.role.value},
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_users)),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="کاربر یافت نشد")

    old_value = {"role": user.role.value, "is_active": user.is_active, "personnel_id": user.personnel_id}
    updates = payload.model_dump(exclude_unset=True, exclude={"password"})

    # محافظ قفل‌شدن: HR نمی‌تواند حساب خودش را غیرفعال کند یا نقش HR خودش را بگیرد؛
    # وگرنه ممکن است هیچ HR فعالی باقی نماند و مدیریت سامانه قفل شود.
    if user.id == current_user.id:
        if updates.get("is_active") is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="نمی‌توانید حساب کاربری خودتان را غیرفعال کنید",
            )
        if "role" in updates and updates["role"] != UserRole.hr:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="نمی‌توانید نقش «منابع انسانی» را از حساب خودتان بگیرید",
            )
    if "personnel_id" in updates and updates["personnel_id"] is not None:
        if db.get(Personnel, updates["personnel_id"]) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="پرسنل انتخاب‌شده یافت نشد"
            )
        # مسیر دوم تداخل ارزیاب/ارزیابی‌شونده: دسترسی درست بوده و حالا کاربرِ ارزیاب
        # به همان پرسنل لینک می‌شود.
        ensure_user_link_is_not_self_evaluation(db, user, updates["personnel_id"])
    for field, value in updates.items():
        setattr(user, field, value)
    if user.role == UserRole.employee and user.personnel_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای نقش «کارمند» باید پرسنل متناظر انتخاب شود",
        )
    # رمز عبور هرگز در لاگ ثبت نمی‌شود؛ فقط این‌که تغییر کرده است
    audited_changes: dict = {k: (v.value if isinstance(v, UserRole) else v) for k, v in updates.items()}
    if payload.password:
        user.password_hash = hash_password(payload.password)
        # نشست‌های فعال قبلی این کاربر بلافاصله باطل می‌شوند
        user.token_version += 1
        revoke_all_for_user(db, user.id)
        # رمز موقتی که HR تعیین کرده باید در اولین ورود توسط خود کاربر عوض شود
        user.must_change_password = True
        audited_changes["password_changed"] = True

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="user_updated",
        old_value=old_value,
        new_value={"id": user.id, "username": user.username, **audited_changes},
    )
    db.commit()
    db.refresh(user)
    return user
