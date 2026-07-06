from pydantic import BaseModel, Field

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
    role: UserRole
    personnel_id: int | None = None
    must_change_password: bool = False
