"""خواندن مجوزها و وضعیت ماژول‌ها (نیمهٔ دوم P0-03)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.modules import MODULES, MODULES_BY_KEY
from app.models.capability import UserCapability
from app.models.enums import Capability
from app.models.module import ModuleSetting


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
