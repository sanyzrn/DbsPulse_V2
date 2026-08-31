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
        display_name=user.display_name,
        role=user.role,
        personnel_id=user.personnel_id,
        must_change_password=user.must_change_password,
    )


def require_own_personnel(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """گاردِ مسیرهای «پروندهٔ خودم» — هر کسی که یک پروندهٔ پرسنلی دارد.

    این‌جا عمداً نقش سنجیده نمی‌شود. هر فهرستِ نقشی که این‌جا نوشته شود، یک
    اشکالِ تکرارشونده می‌سازد: اول `employee` بود و مسئولِ واحد — که خودش هم
    ارزیابی می‌شود — روی همهٔ مسیرهای `/api/me` ۴۰۳ می‌گرفت؛ بعد فهرست به چهار
    نقش گسترده شد و همان ۴۰۳ برای معاونت و مدیرعامل ماند.

    ریشه‌اش این است که «نقش» دو چیزِ بی‌ربط را هم‌زمان تعیین می‌کرد: در زنجیرهٔ
    ارزیابی چه کاری می‌کنی، و آیا خودت ارزیابی می‌شوی. استثنای واقعی فقط یکی
    است — *ثبتِ* خودارزیابی برای مدیرعامل و معاونت‌ها — و جایش
    `services/self_assessment.may_self_assess` است، نه گاردِ مسیر.

    دسترسی را باز نمی‌کند: هر مسیر همچنان فقط پروندهٔ *همین شخص* را برمی‌گرداند
    و پروندهٔ دیگران ۴۰۴ می‌گیرد. این‌جا فقط گلوگاهِ «اصلاً پروندهٔ پرسنلی داری؟»
    است.
    """
    if current_user.personnel_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "حساب شما به پروندهٔ پرسنلی وصل نیست، پس پروندهٔ ارزیابی‌ای هم ندارد. "
                "منابع انسانی می‌تواند این اتصال را برقرار کند."
            ),
        )
    return current_user


def require_roles(*allowed_roles: UserRole):
    def dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما اجازه دسترسی به این بخش را ندارید",
            )
        return current_user

    return dependency


def require_chain_stage(stage_role: UserRole):
    """گاردِ یک *مرحله* از زنجیرهٔ ارزیابی، نه یک نقشِ دقیق.

    `require_roles(unit_supervisor)` می‌گفت «فقط کسی که نقشش دقیقاً مسئول واحد
    است». ولی در یک سازمان واقعی، مدیرعامل ممکن است برای چند نفر خودش مسئول
    مستقیم باشد و معاونت برای چند نفر نمره‌دهندهٔ اول. با گاردِ نقشِ دقیق، چنین
    آدمی *اصلاً قابل تنظیم نبود*.

    این گارد دسترسی را باز نمی‌کند: اقدام روی یک پروندهٔ مشخص همچنان به این بند
    است که شناسهٔ همان شخص در همان مرحله از زنجیرهٔ آن پرونده نشسته باشد — که
    `apply_transition` می‌سنجد. این‌جا فقط گلوگاهِ «آیا اصلاً چنین جایگاهی
    می‌توانی داشته باشی» است.
    """

    def dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        from app.services.workflow import may_act_at

        if not may_act_at(current_user.role, stage_role):
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


def require_role_or_capability(role: UserRole, capability: Capability):
    """یا در آن نقش هستی، یا مجوزش را داری.

    برای کارهایی که هم بخشی از کارِ روزمرهٔ یک نقش‌اند و هم بخشی از راه‌اندازیِ
    سامانه. نمونهٔ روشنش پرسنل است: ثبتِ پرسنل کارِ هر روزِ منابع انسانی است، ولی
    مدیر سامانه هم باید بتواند انجامش بدهد — وگرنه حسابِ معاونت و مدیرعامل را
    می‌سازد و هیچ پرسنلی برای وصل‌کردن به آن‌ها ندارد.

    گاردِ نقشِ تنها این را نمی‌داد و گاردِ مجوزِ تنها یعنی باید به همهٔ کاربران
    منابع انسانی یک مجوز تازه بدهیم تا کارِ امروزشان نشکند.
    """

    def dependency(
        current_user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> CurrentUser:
        if current_user.role is role:
            return current_user
        if capability in capabilities_of(db, current_user.id):
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="برای این کار مجوز لازم را ندارید؛ از مدیر سامانه بخواهید آن را به شما بدهد",
        )

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


def audit_log_reader(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """دو راهِ مشروعِ رسیدن به لاگ ممیزی — هر دو با مجوز، نه با نقش.

    `view_audit_log` کل لاگ را می‌دهد، شامل ردیف‌هایی که امتیاز و نتیجهٔ پرونده
    را در خود دارند. `view_diagnostics` فقط رویدادهای سامانه‌ای را — عیب‌یابیِ
    «چرا این حساب وارد نمی‌شود» به نمرهٔ کسی نیاز ندارد. این گارد فقط می‌گوید
    *حق ورود داری*؛ اینکه *چه چیزی می‌بینی* را خودِ endpoint تعیین می‌کند.

    تا پیش از این شرط اول `role is hr` بود، نه یک مجوز. یعنی دسترسی به کامل‌ترین
    ردِ تصمیم‌ها به کسی گره خورده بود که خودش در زنجیرهٔ تصمیم می‌ایستد، و
    گرفتنش از او هیچ راهی نداشت جز عوض‌کردن نقشش. حالا مثل هر اختیار اداری
    دیگری داده و گرفته می‌شود.

    صریح نوشته شده و نه با یک `require_any` عمومی: نسخهٔ عمومی باید امضای هر
    گارد را با گرفتنِ TypeError حدس می‌زد، که تا روزی کار می‌کند که یکی از
    گاردها به دلیل دیگری TypeError بدهد و بی‌صدا از گارد رد شود.
    """
    held = capabilities_of(db, current_user.id)
    if Capability.view_audit_log in held or Capability.view_diagnostics in held:
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="شما اجازه دسترسی به این بخش را ندارید",
    )
