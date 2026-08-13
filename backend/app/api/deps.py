from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import CurrentUser

bearer_scheme = HTTPBearer(auto_error=False)

# تنها مسیرهایی که کاربرِ ملزم‌به‌تغییر‌رمز هم می‌تواند صدا بزند — وگرنه راه خروجی از
# این وضعیت ندارد. لیست عمداً allowlist است نه blocklist: هر endpoint جدیدی به‌صورت
# پیش‌فرض بسته می‌ماند و کسی یادش نمی‌رود گارد را اضافه کند.
_FORCED_PASSWORD_CHANGE_EXEMPT_PATHS = frozenset(
    {
        "/api/auth/change-password",
        "/api/auth/me",
    }
)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="توکن نامعتبر یا منقضی‌شده است",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise unauthorized

    # sub باید یک شناسهٔ عددی معتبر باشد؛ توکن دست‌کاری‌شده با sub غیرعددی نباید
    # به یک 500 (ValueError کنترل‌نشده) منجر شود، بلکه همان 401 استاندارد را بگیرد.
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise unauthorized from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    if payload.get("tv") != user.token_version:
        raise unauthorized

    # «تغییر اجباری رمز» تا امروز فقط یک ریدایرکت در فرانت بود؛ یعنی هر کسی که
    # مستقیم به API درخواست می‌زد آن را دور می‌زد. حساب‌هایی که رمزشان را HR ریست
    # کرده (یا حساب دموی بازمانده) دقیقاً همان‌هایی‌اند که نباید بدون تغییر رمز کار کنند.
    if user.must_change_password and request.url.path not in _FORCED_PASSWORD_CHANGE_EXEMPT_PATHS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="پیش از استفاده از سامانه باید رمز عبور خود را تغییر دهید",
        )

    return CurrentUser(
        id=user.id,
        username=user.username,
        role=user.role,
        personnel_id=user.personnel_id,
        must_change_password=user.must_change_password,
    )


def require_roles(*allowed_roles: UserRole):
    def dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما اجازه دسترسی به این بخش را ندارید",
            )
        return current_user

    return dependency
