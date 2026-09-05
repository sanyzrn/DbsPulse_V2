from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_capability
from app.core.security import hash_password
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.auth_session import AuthSession
from app.models.capability import UserCapability
from app.models.enums import Capability, UserRole
from app.models.notification import Notification
from app.models.personnel import Personnel
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.schemas.user import UserCreate, UserPage, UserRead, UserUpdate
from app.services.audit import log_event
from app.services.authorization import apply_default_hr_capabilities
from app.services.excel import build_users_workbook
from app.services.self_evaluation import ensure_user_link_is_not_self_evaluation
from app.services.sessions import revoke_all_for_user

router = APIRouter(prefix="/api/users", tags=["users"])


def _apply_user_filters(query, *, role: UserRole | None, q: str | None, is_active: bool | None):
    if role is not None:
        query = query.where(User.role == role)
    if q:
        # نام هم جست‌وجو می‌شود، نه فقط نام کاربری: کسی که دنبال «رضایی» می‌گردد
        # نمی‌داند نام کاربری‌اش dep1 است — و همین باعث می‌شد فهرست خالی برگردد.
        needle = f"%{q.strip()}%"
        query = query.where(User.username.ilike(needle) | User.full_name.ilike(needle))
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    return query


def _linked_names(db: Session, users: list[User]) -> dict[int, str]:
    """نام پرسنلِ حساب‌های وصل‌شده، با یک کوئری برای کل صفحه (نه N+1)."""
    personnel_ids = {u.personnel_id for u in users if u.personnel_id is not None}
    if not personnel_ids:
        return {}
    return dict(
        db.execute(
            select(Personnel.id, Personnel.full_name).where(Personnel.id.in_(personnel_ids))
        ).all()
    )


def _to_read(users: list[User], linked_names: dict[int, str]) -> list[UserRead]:
    """پروندهٔ پرسنلی مرجع نام است، اگر باشد.

    وگرنه HR می‌تواند نام یک نفر را در پروندهٔ پرسنلی اصلاح کند و صفحهٔ کاربران
    همچنان نام قدیمی را نشان بدهد — دو منبع حقیقت، که دیر یا زود از هم دور
    می‌افتند.
    """
    items = []
    for user in users:
        item = UserRead.model_validate(user)
        linked = linked_names.get(user.personnel_id) if user.personnel_id else None
        if linked:
            item.display_name = linked
        items.append(item)
    return items


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
    return UserPage(total=total, items=_to_read(items, _linked_names(db, items)))


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
    personnel_names = _linked_names(db, users)
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
) -> UserRead:
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
        full_name=(payload.full_name or "").strip() or None,
        is_active=True,
    )
    db.add(user)
    db.flush()
    if user.role == UserRole.hr:
        apply_default_hr_capabilities(db, user.id)
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="user_created",
        new_value={"id": user.id, "username": user.username, "role": user.role.value},
    )
    db.commit()
    db.refresh(user)
    return _to_read([user], _linked_names(db, [user]))[0]


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_users)),
) -> UserRead:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="کاربر یافت نشد")

    old_value = {
        "role": user.role.value,
        "is_active": user.is_active,
        "personnel_id": user.personnel_id,
        "full_name": user.full_name,
    }
    updates = payload.model_dump(exclude_unset=True, exclude={"password"})

    # محافظ قفل‌شدن: HR نمی‌تواند حساب خودش را غیرفعال کند یا نقش HR خودش را بگیرد؛
    # وگرنه ممکن است هیچ HR فعالی باقی نماند و مدیریت سامانه قفل شود.
    if user.id == current_user.id:
        if updates.get("is_active") is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="نمی‌توانید حساب کاربری خودتان را غیرفعال کنید",
            )
        if "role" in updates and updates["role"] != user.role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="نمی‌توانید نقش حساب کاربری خودتان را تغییر دهید",
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
    if old_value["role"] != UserRole.hr.value and user.role == UserRole.hr:
        apply_default_hr_capabilities(db, user.id)
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
    return _to_read([user], _linked_names(db, [user]))[0]


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_users)),
) -> Response:
    """حذف کامل حساب — فقط برای حسابی که هیچ ردی از خود نگذاشته.

    مرزِ این کار عمدی است. حسابی که یک بار وارد شده، در لاگ ممیزی ردیف دارد، و آن
    لاگ یک زنجیرهٔ هش است: پاک‌کردن یک ردیفش یعنی از آن نقطه به بعد هیچ‌کدام از
    ردیف‌ها دیگر قابل اثبات نیستند. همان چیزی که کل لاگ برایش وجود دارد.

    پس دو کار داریم و هر دو لازم‌اند:

    * **حذف** برای حسابی که اشتباه ساخته شده — نقش غلط، نام کاربری غلط، یا
      اصلاً آدمش عوض شده. چیزی برای نگه‌داشتن ندارد و ماندنش فقط فهرست را شلوغ
      می‌کند.
    * **غیرفعال‌کردن** برای حسابی که کار کرده. دسترسی‌اش قطع می‌شود ولی تاریخ
      می‌ماند: پرونده‌هایی که تأیید کرده همچنان می‌گویند چه کسی تأییدشان کرده.

    اگر حذف ممکن نباشد، پیام خطا دقیقاً همین را می‌گوید و راه دوم را پیشنهاد
    می‌دهد — نه یک «خطای داخلی سرور» که کاربر نداند با آن چه کند.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="کاربر یافت نشد")
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نمی‌توانید حساب کاربری خودتان را حذف کنید",
        )

    has_history = db.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.actor_user_id == user.id)
    )
    if has_history:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "این حساب در گزارش رویدادها رد دارد و حذفش تاریخِ ثبت‌شده را از بین می‌برد. "
                "به‌جای حذف، آن را «غیرفعال» کنید: دسترسی‌اش بسته می‌شود و سابقه‌اش می‌ماند."
            ),
        )

    # متعلقاتِ خودِ حساب با آن می‌روند؛ این‌ها چیزی دربارهٔ *کارِ* او نمی‌گویند.
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.execute(delete(Notification).where(Notification.user_id == user.id))
    db.execute(delete(UserCapability).where(UserCapability.user_id == user.id))
    db.execute(delete(UserCapability).where(UserCapability.granted_by_user_id == user.id))

    snapshot = {"id": user.id, "username": user.username, "role": user.role.value}
    db.delete(user)
    try:
        db.flush()
    except IntegrityError:
        # جدولی که هنوز به این حساب اشاره می‌کند و بالا ندیدیمش. دیتابیس مرجعِ
        # این پرسش است، نه فهرستی که در کد نگه می‌داریم و از دنیا عقب می‌افتد.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "این حساب هنوز در پرونده‌های ارزیابی یا زنجیرهٔ ارزیابیِ کسی استفاده می‌شود. "
                "ابتدا جای او را به فرد دیگری بسپارید، یا حساب را «غیرفعال» کنید."
            ),
        ) from None

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="user_deleted",
        old_value=snapshot,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
