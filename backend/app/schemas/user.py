from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import UserRole

# طبق NIST 800-63B: حداقل طول به‌جای قوانین ترکیبی پیچیده
_PASSWORD_MIN_LENGTH = 10
_USERNAME_PATTERN = r"^[a-zA-Z0-9_.\-]{3,64}$"


class UserCreate(BaseModel):
    username: str = Field(pattern=_USERNAME_PATTERN)
    password: str = Field(min_length=_PASSWORD_MIN_LENGTH)
    role: UserRole
    personnel_id: int | None = None

    @model_validator(mode="after")
    def _employee_requires_personnel(self) -> "UserCreate":
        # بدون پیوند به پرسنل، حساب «کارمند» هیچ کارنامه‌ای نخواهد داشت
        if self.role == UserRole.employee and self.personnel_id is None:
            raise ValueError("برای نقش «کارمند» باید پرسنل متناظر انتخاب شود")
        return self


class UserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=_PASSWORD_MIN_LENGTH)
    personnel_id: int | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: UserRole
    is_active: bool
    personnel_id: int | None
    created_at: datetime


class UserPage(BaseModel):
    total: int
    items: list[UserRead]
