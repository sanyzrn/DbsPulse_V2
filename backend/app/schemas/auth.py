from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import UserRole


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    """refresh token عمداً در بدنه پاسخ نیست؛ فقط به‌صورت کوکی HttpOnly ست می‌شود
    تا از دسترس اسکریپت‌ها (XSS) خارج باشد."""

    access_token: str
    token_type: str = "bearer"
    role: UserRole
    must_change_password: bool = False


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10)


class CurrentUser(BaseModel):
    id: int
    username: str
    # نامی که در نوار بالای صفحه دیده می‌شود. اگر روی حساب ثبت نشده باشد همان
    # نام کاربری است، پس همیشه مقدار دارد و UI لازم نیست fallback بنویسد.
    display_name: str = ""
    role: UserRole
    personnel_id: int | None = None
    must_change_password: bool = False


class SessionRead(BaseModel):
    """یک نشست فعال، آن‌قدر که کاربر بتواند تشخیصش بدهد.

    jti عمداً برنمی‌گردد: شناسهٔ عددیِ ردیف برای «این یکی را ببند» کافی است، و
    خودِ jti بخشی از یک توکن زنده است که نباید در پاسخ API پخش شود.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_agent: str | None
    ip: str | None
    created_at: datetime
    last_used_at: datetime | None
    # آیا همین نشستی است که این درخواست با آن آمده؟ بدون این، کاربر نمی‌داند
    # کدام ردیف را نباید ببندد.
    is_current: bool = False
