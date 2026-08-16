"""شکل پاسخ‌های مدیریت سامانه (نیمهٔ دوم P0-03)."""
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import Capability, UserRole


class MyPermissions(BaseModel):
    """آنچه فرانت‌اند باید بداند تا منو را درست بچیند."""

    capabilities: list[str]
    #: کلید ماژول -> روشن/خاموش
    modules: dict[str, bool]


class CapabilityHolder(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    role: UserRole
    is_active: bool
    capabilities: list[str]


class CapabilityGrant(BaseModel):
    """مجموعهٔ *کامل* مجوزهای کاربر — نه افزودن و کاستن.

    جایگزینی کامل عمدی است: با «افزودن/کاستن»، دو درخواست هم‌زمان می‌توانستند
    نتیجه‌ای بسازند که هیچ‌کدام نخواسته بودند.
    """

    capabilities: list[str] = Field(default_factory=list)

    @field_validator("capabilities")
    @classmethod
    def _known(cls, values: list[str]) -> list[str]:
        valid = {c.value for c in Capability}
        unknown = [v for v in values if v not in valid]
        if unknown:
            raise ValueError(f"مجوز ناشناخته: {'، '.join(unknown)}")
        return values


class ModuleState(BaseModel):
    key: str
    label: str
    description: str
    enabled: bool


class ModuleToggle(BaseModel):
    enabled: bool


class OverlappingUser(BaseModel):
    """حسابی که هم در زنجیرهٔ ارزیابی جایگاه دارد و هم قواعد را عوض می‌کند."""

    username: str
    role: UserRole
    capabilities: list[str]


class SeparationStatus(BaseModel):
    """آیا تفکیک وظایف واقعاً برقرار است.

    `separated=False` خطا نیست — حالتِ پیش‌فرضِ سازگار با گذشته است. ولی باید
    *دیده* شود، وگرنه سازوکاری ساخته‌ایم که هیچ‌وقت روشن نمی‌شود.
    """

    separated: bool
    overlapping_users: list[OverlappingUser]
    #: چند حساب اختصاصیِ مدیریت (نقش پشتیبانی با مجوز) وجود دارد
    dedicated_admin_count: int
