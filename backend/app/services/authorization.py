"""خواندن مجوزها و وضعیت ماژول‌ها (نیمهٔ دوم P0-03)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.modules import MODULES, MODULES_BY_KEY
from app.models.capability import UserCapability
from app.models.enums import Capability
from app.models.module import ModuleSetting

DEFAULT_HR_CAPABILITIES = frozenset(
    {
        Capability.manage_users,
        Capability.manage_personnel,
        Capability.manage_scoring,
    }
)


def capabilities_of(db: Session, user_id: int) -> set[Capability]:
    return set(
        db.scalars(select(UserCapability.capability).where(UserCapability.user_id == user_id))
    )


def has_capability(db: Session, user_id: int, capability: Capability) -> bool:
    return (
        db.scalar(
            select(UserCapability.id).where(
                UserCapability.user_id == user_id,
                UserCapability.capability == capability,
            )
        )
        is not None
    )


def apply_default_hr_capabilities(db: Session, user_id: int) -> list[Capability]:
    """پایهٔ منابع انسانی را *اضافه* می‌کند — و هیچ‌چیزی را برنمی‌دارد.

    نسخهٔ پیشین اول همهٔ ردیف‌های این حساب را پاک می‌کرد و بعد سه مجوز پایه را
    می‌نوشت. سه پیامد داشت که هر سه دیده شدند:

    * تغییر نقشِ یک حسابِ مدیر سامانه به «منابع انسانی» شش مجوزش را می‌شست،
      از جمله `manage_capabilities`.
    * اگر آن حساب تنها اختیاردهندهٔ فعال بود، دیگر هیچ‌کس نمی‌توانست به هیچ‌کس
      اختیاری بدهد — و گاردِ «آخرین اختیاردهنده نمی‌تواند خودش را خلع کند» که
      روی endpointِ مجوزها هست، این مسیر را اصلاً نمی‌دید.
    * هیچ‌کدام در گزارش رویدادها ثبت نمی‌شد؛ تنها ردِ ماجرا یک `user_updated`
      بود که فقط نقش را می‌گفت.

    «پیش‌فرض» یعنی کفِ اختیارات، نه سقفِ آن. برداشتنِ مجوز کارِ صریحِ صفحهٔ
    مجوزهاست، که ثبتش هم می‌کند.

    فهرستِ آنچه *واقعاً* اضافه شد برگردانده می‌شود تا فراخوان بتواند همان را در
    لاگ ممیزی بنویسد — و ردیفی که چیزی عوض نکرده، رویدادی هم نسازد.
    """
    existing = capabilities_of(db, user_id)
    added = sorted(DEFAULT_HR_CAPABILITIES - existing, key=lambda c: c.value)
    db.add_all(
        UserCapability(user_id=user_id, capability=capability) for capability in added
    )
    return added


def module_states(db: Session) -> dict[str, bool]:
    """وضعیت همهٔ ماژول‌ها. ماژولی که ردیفی ندارد، پیش‌فرضِ خودش را می‌گیرد.

    یعنی افزودن یک ماژول تازه به کد، بدون مایگریشن کار می‌کند — و مهم‌تر،
    ماژولِ تازه با حالتِ درستش شروع می‌شود نه با «خاموش» فقط چون ردیف ندارد.
    """
    stored = {row.key: row.enabled for row in db.scalars(select(ModuleSetting))}
    return {
        module.key: stored.get(module.key, module.default_enabled)
        for module in MODULES
    }


def is_module_enabled(db: Session, key: str) -> bool:
    row = db.get(ModuleSetting, key)
    if row is not None:
        return row.enabled
    module = MODULES_BY_KEY.get(key)
    return module.default_enabled if module else True
