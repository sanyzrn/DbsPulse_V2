import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.metrics import auth_failures
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    ChangePasswordRequest,
    CurrentUser,
    LoginRequest,
    LoginResponse,
)
from app.services.audit import log_event
from app.services.login_guard import (
    clear_failures,
    locked_until,
    notify_hr_of_lockout,
    record_failure,
)
from app.services.sessions import (
    RefreshReuseError,
    create_session,
    revoke_all_for_user,
    revoke_session,
    rotate_session,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

REFRESH_COOKIE = "dbspulse_refresh"

# برای کاربر ناموجود هم یک verify واقعی انجام می‌دهیم تا از روی زمان پاسخ نتوان
# نام‌های کاربری معتبر را حدس زد (timing attack).
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_hex(16))


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    # کوکی HttpOnly: از دسترس جاوااسکریپت (XSS) خارج است. SameSite=strict + مسیر
    # محدود به /api/auth یعنی فقط با درخواست‌های same-site به مسیرهای auth ارسال می‌شود.
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        samesite="strict",
        secure=settings.environment == "production",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/auth",
    )


def _issue_login_response(response: Response, db: Session, user: User) -> LoginResponse:
    jti = create_session(db, user.id)
    db.commit()
    _set_refresh_cookie(
        response, create_refresh_token(user.id, user.role.value, user.token_version, jti)
    )
    return LoginResponse(
        access_token=create_access_token(user.id, user.role.value, user.token_version),
        role=user.role,
        must_change_password=user.must_change_password,
    )


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> LoginResponse:
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="نام کاربری یا رمز عبور اشتباه است",
    )
    client_ip = request.client.host if request.client else None

    # قفل حساب پیش از هر کاری بررسی می‌شود — حتی رمز درست هم در پنجرهٔ قفل پذیرفته
    # نمی‌شود، وگرنه مهاجمی که رمز را همان تلاش آخر پیدا کرده از قفل عبور می‌کرد.
    lock_expiry = locked_until(db, payload.username)
    if lock_expiry is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "به دلیل تلاش‌های ناموفق پیاپی، ورود به این حساب موقتاً قفل شده است؛ "
                f"{settings.login_lockout_minutes} دقیقه دیگر دوباره تلاش کنید."
            ),
            headers={"Retry-After": str(settings.login_lockout_minutes * 60)},
        )

    def _fail(user_id: int | None) -> None:
        """شکست را می‌شمارد و در صورت رسیدن به آستانه قفل می‌کند + به HR خبر می‌دهد."""
        auth_failures.labels(reason="bad_credentials").inc()
        locked = record_failure(db, payload.username)
        if user_id is not None:
            log_event(
                db, actor_user_id=user_id, event_type="login_failed", new_value={"ip": client_ip}
            )
        if locked is not None:
            if user_id is not None:
                log_event(
                    db,
                    actor_user_id=user_id,
                    event_type="account_locked",
                    new_value={"ip": client_ip, "until": locked.isoformat()},
                )
            notify_hr_of_lockout(db, payload.username, locked)
        db.commit()

    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None:
        # نام کاربری ناموجود هم شمرده می‌شود، وگرنه خودِ رفتار قفل به یک اوراکل
        # «این حساب وجود دارد» تبدیل می‌شد.
        verify_password(payload.password, _DUMMY_PASSWORD_HASH)
        _fail(None)
        raise invalid_credentials
    if not verify_password(payload.password, user.password_hash):
        _fail(user.id)
        raise invalid_credentials
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="حساب کاربری غیرفعال است"
        )

    clear_failures(db, payload.username)
    log_event(
        db,
        actor_user_id=user.id,
        event_type="login_succeeded",
        new_value={"ip": client_ip},
    )
    return _issue_login_response(response, db, user)


@router.post("/refresh", response_model=AccessTokenResponse)
@limiter.limit("30/minute")
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="نشست نامعتبر یا منقضی‌شده است"
    )
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise unauthorized
    data = decode_token(token)
    if data is None or data.get("type") != "refresh" or not data.get("jti"):
        raise unauthorized

    user = db.get(User, int(data["sub"]))
    if user is None or not user.is_active:
        raise unauthorized
    if data.get("tv") != user.token_version:
        raise unauthorized

    try:
        new_jti = rotate_session(db, user.id, data["jti"])
        db.commit()
    except RefreshReuseError:
        # استفاده دوباره از توکن چرخیده/باطل = نشانه سرقت؛ همه نشست‌ها باطل شدند
        db.commit()
        raise unauthorized from None

    if new_jti is not None:
        _set_refresh_cookie(
            response, create_refresh_token(user.id, user.role.value, user.token_version, new_jti)
        )

    return AccessTokenResponse(
        access_token=create_access_token(user.id, user.role.value, user.token_version)
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        data = decode_token(token)
        if data is not None and data.get("type") == "refresh" and data.get("jti"):
            revoke_session(db, data["jti"])
            db.commit()
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")


@router.post("/change-password", response_model=LoginResponse)
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> LoginResponse:
    user = db.get(User, current_user.id)
    if user is None or not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="رمز عبور فعلی اشتباه است"
        )
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="رمز عبور جدید نباید با رمز فعلی یکسان باشد"
        )
    # نام کاربری داخل رمز، رمز را عملاً حدس‌زدنی می‌کند و اولین چیزی است که هر
    # فهرست حملهٔ آماده امتحان می‌کند. فرم هم همین را نشان می‌دهد؛ اگر فقط سمت
    # کلاینت بررسی می‌شد، یک درخواست مستقیم دورش می‌زد و رابط کاربری دربارهٔ
    # قانون دروغ گفته بود.
    if len(user.username) >= 3 and user.username.lower() in payload.new_password.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="رمز عبور جدید نباید شامل نام کاربری باشد",
        )

    user.password_hash = hash_password(payload.new_password)
    # تمام نشست‌ها و توکن‌های قبلی (همه دستگاه‌ها) باطل می‌شوند
    user.token_version += 1
    user.must_change_password = False
    revoke_all_for_user(db, user.id)
    log_event(db, actor_user_id=user.id, event_type="password_changed_self")
    return _issue_login_response(response, db, user)


@router.get("/me", response_model=CurrentUser)
def me(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return current_user
