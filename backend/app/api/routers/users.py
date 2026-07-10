from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.security import hash_password
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.personnel import Personnel
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.schemas.user import UserCreate, UserPage, UserRead, UserUpdate
from app.services.audit import log_event
from app.services.sessions import revoke_all_for_user

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=UserPage)
def list_users(
    role: UserRole | None = None,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> UserPage:
    query = select(User)
    if role is not None:
        query = query.where(User.role == role)
    if q:
        query = query.where(User.username.ilike(f"%{q.strip()}%"))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.order_by(User.username).limit(limit).offset(offset)))
    return UserPage(total=total, items=[UserRead.model_validate(u) for u in items])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
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
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
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
