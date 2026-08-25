"""تضمینِ اینکه همیشه یک حسابِ مدیر سامانه وجود دارد.

مسئله
-----
تا امروز ساختِ اولین حساب یک کارِ دستی بود (`scripts.create_admin`). یعنی روی یک
نصب تازه، سرویس بالا می‌آمد و **هیچ‌کس نمی‌توانست وارد شود** تا کسی آن اسکریپت را
اجرا کند. بدتر از آن، حالتِ قفل‌شدن هم راهِ خروج نداشت: اگر تنها حساب مدیر
غیرفعال یا حذف می‌شد، تنها راه برگشت SQL دستی روی دیتابیس بود.

پس این ماژول در هر بالا آمدنِ سرویس یک پرسش می‌پرسد: «آیا حسابِ فعالی هست که
بتواند مجوز بدهد؟» اگر نه، یکی می‌سازد.

رمز عبور
--------
هرگز رمزِ ثابت. سامانه‌ای که با رمز پیش‌فرضِ معلوم بالا بیاید، از روز اول عمومی
است — و این همان چیزی است که مایگریشن حذفِ حساب‌های دمو برای بستنش نوشته شد.

دو راه، به همین ترتیب:

* `DBSPULSE_ADMIN_PASSWORD` اگر تنظیم شده باشد (برای استقرار خودکار).
* وگرنه یک رمزِ تصادفیِ قوی که **یک بار** در لاگِ سرویس نوشته می‌شود. اگر کسی آن
  خط را ندید، حساب ساخته شده ولی رمزش را کسی نمی‌داند؛ راهِ درستش این است که
  همان اسکریپتِ دستی رمز را عوض کند. این عمدی است: چاپِ دوبارهٔ رمز در هر
  ری‌استارت، رمز را به لاگ‌ها می‌سپارد.

در هر دو حالت `must_change_password` روشن است، پس اولین ورود به تغییر رمز
می‌رسد و رمزِ لاگ‌شده کوتاه‌عمر است.

نقش
---
`support` و نه `hr` — طبق P0-03 نقش می‌گوید در *زنجیرهٔ ارزیابی* کجا ایستاده‌ای،
و این حساب هیچ‌جا نمی‌ایستد. مجوزها را دارد، نمرهٔ کسی را نمی‌بیند.
"""
from __future__ import annotations

import logging
import os
import secrets
import string

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.capability import UserCapability
from app.models.enums import Capability, UserRole
from app.models.user import User

logger = logging.getLogger("dbspulse")

PASSWORD_ENV = "DBSPULSE_ADMIN_PASSWORD"
USERNAME_ENV = "DBSPULSE_ADMIN_USERNAME"
DEFAULT_USERNAME = "admin"

#: حروف و رقم‌ها به‌علاوهٔ چند نشانه — بدون کاراکترهایی که در ترمینال و کپی/پیست
#: دردسر می‌سازند (نقل‌قول، بک‌اسلش، فاصله).
_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*-_=+"


def _generate_password(length: int = 20) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def _unique_username(db: Session, base: str) -> str:
    """`admin`، وگرنه `admin2`، `admin3`…

    نامِ گرفته‌شده ممکن است حسابِ غیرفعالی باشد که همین حالا دلیلِ نبودِ مدیر
    است. عوض‌کردنِ آن حساب کارِ این تابع نیست — ساختنِ یک حسابِ تازه است.
    """
    if db.scalar(select(User).where(User.username == base)) is None:
        return base
    for suffix in range(2, 100):
        candidate = f"{base}{suffix}"
        if db.scalar(select(User).where(User.username == candidate)) is None:
            return candidate
    raise RuntimeError("نام کاربری آزادی برای حساب مدیر پیدا نشد")


def has_active_admin(db: Session) -> bool:
    """آیا حسابِ فعالی هست که بتواند مجوز بدهد؟

    معیار عمداً `manage_capabilities` است، نه «نقش support». نقش چیزی دربارهٔ
    اختیار نمی‌گوید؛ این مجوز تنها چیزی است که بدونش سامانه واقعاً قفل می‌شود،
    چون هیچ‌کس نمی‌تواند به هیچ‌کس اختیاری بدهد.
    """
    return (
        db.scalar(
            select(User.id)
            .join(UserCapability, UserCapability.user_id == User.id)
            .where(
                User.is_active.is_(True),
                UserCapability.capability == Capability.manage_capabilities,
            )
            .limit(1)
        )
        is not None
    )


def ensure_bootstrap_admin(db: Session) -> str | None:
    """اگر مدیری نیست، یکی بساز. نام کاربریِ ساخته‌شده را برمی‌گرداند.

    اگر مدیری هست، هیچ کاری نمی‌کند و `None` برمی‌گرداند — یعنی این تابع در هر
    بالا آمدنِ عادیِ سرویس بی‌اثر است.
    """
    if has_active_admin(db):
        return None

    password = os.environ.get(PASSWORD_ENV) or ""
    generated = not password
    if generated:
        password = _generate_password()

    username = _unique_username(db, os.environ.get(USERNAME_ENV) or DEFAULT_USERNAME)
    admin = User(
        username=username,
        password_hash=hash_password(password),
        role=UserRole.support,
        full_name="مدیر سامانه",
        is_active=True,
        # رمزی که یا در لاگ نوشته شده یا در متغیر محیطی است، باید در اولین ورود
        # عوض شود. بدون این، رمزِ راه‌اندازی برای همیشه رمزِ حساب می‌ماند.
        must_change_password=True,
    )
    db.add(admin)
    db.flush()
    for capability in Capability:
        db.add(UserCapability(user_id=admin.id, capability=capability))
    # commit با فراخوان است، نه با این تابع: تراکنش مالِ کسی است که بازش کرده.
    db.flush()

    if generated:
        logger.warning(
            "\n%s\n  هیچ حساب مدیری وجود نداشت؛ یک حساب ساخته شد.\n"
            "  نام کاربری: %s\n  رمز عبور موقت: %s\n"
            "  این رمز فقط همین یک بار نوشته می‌شود و در اولین ورود باید عوض شود.\n%s",
            "=" * 62,
            username,
            password,
            "=" * 62,
        )
    else:
        logger.warning(
            "هیچ حساب مدیری وجود نداشت؛ حساب «%s» با رمزِ %s ساخته شد.",
            username,
            PASSWORD_ENV,
        )
    return username
