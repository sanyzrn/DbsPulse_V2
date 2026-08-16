from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.enums import Capability, UserRole
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.services.authorization import capabilities_of, is_module_enabled

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


def require_capability(*required: Capability):
    """گاردِ مجوز اداری، مستقل از نقش (نیمهٔ دوم P0-03).

    عمداً نقش را نگاه نمی‌کند: `hr` هم اگر مجوز نداشته باشد رد می‌شود. تنها راهِ
    داشتنِ اختیار، داشتنِ خودِ مجوز است — همان چیزی که «مدیر سامانه» را از
    «کاربر پرمشغله» جدا می‌کند.

    مایگریشن این قابلیت، همهٔ مجوزها را به کاربران HR موجود داده تا هیچ استقراری
    نشکند؛ سازمانی که می‌خواهد تفکیک کند، از HR می‌گیرد و به حساب پشتیبانی می‌دهد.
    """

    def dependency(
        current_user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> CurrentUser:
        held = capabilities_of(db, current_user.id)
        missing = [c for c in required if c not in held]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="برای این کار مجوز لازم را ندارید؛ از مدیر سامانه بخواهید آن را به شما بدهد",
            )
        return current_user

    return dependency


def require_module(key: str):
    """گاردِ ماژول خاموش‌شده.

    روی نوشتن‌ها می‌نشیند نه خواندن‌ها: خاموش‌کردن یک ماژول نباید دادهٔ موجود را
    از دسترس خارج کند — فقط جلوی *افزودن* تازه را می‌گیرد. سوییچی که داده را
    ناپیدا کند، سوییچ نیست.
    """

    def dependency(db: Session = Depends(get_db)) -> None:
        if not is_module_enabled(db, key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="این بخش توسط مدیر سامانه غیرفعال شده است",
            )

    return dependency


def hr_or_diagnostics(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """دو راهِ مشروعِ رسیدن به لاگ ممیزی.

    منابع انسانی به‌عنوان کارِ خودش («چه کسی این پرونده را برگرداند و چرا»)، و
    پشتیبانی فنی برای عیب‌یابی («چرا فلانی نمی‌تواند وارد شود»). این گارد فقط
    می‌گوید *حق ورود داری*؛ این‌که *چه چیزی می‌بینی* را خودِ endpoint تعیین
    می‌کند — پشتیبانی تنها رویدادهای سامانه‌ای را.

    صریح نوشته شده و نه با یک `require_any` عمومی: نسخهٔ عمومی باید امضای هر
    گارد را با گرفتنِ TypeError حدس می‌زد، که تا روزی کار می‌کند که یکی از
    گاردها به دلیل دیگری TypeError بدهد و بی‌صدا از گارد رد شود.
    """
    if current_user.role is UserRole.hr:
        return current_user
    if Capability.view_diagnostics in capabilities_of(db, current_user.id):
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="شما اجازه دسترسی به این بخش را ندارید",
    )
