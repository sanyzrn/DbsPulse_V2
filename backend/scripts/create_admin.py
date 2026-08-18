"""ساخت اولین حساب مدیر سامانه، روی دیتابیسی که هیچ کاربری ندارد.

چرا این فایل هست
----------------
تا امروز تنها راهِ داشتنِ حساب، مایگریشن سیدِ دمو بود — و آن مایگریشن با
`SEED_DEMO_DATA=false` (یعنی هر چیزی که دمو نباشد) عمداً هیچ کاربری نمی‌سازد.
نتیجه: روی یک نصب واقعی، دیتابیس بالا می‌آمد و *هیچ‌کس نمی‌توانست وارد شود*.
راهِ در دسترس هم «همان حساب‌های دمو با رمز عمومی» بود، که دقیقاً چیزی است که
مایگریشن a1d7f4e9b602 برای بستنش نوشته شده.

چه نقشی، و چرا
--------------
پیش‌فرض `support` است، نه `hr`. طبق P0-03 نقش می‌گوید در *زنجیرهٔ ارزیابی* کجا
ایستاده‌ای، و `support` عمداً هیچ‌جا نایستاده — در هیچ گاردِ گردش‌کاری فهرست
نشده و پیش‌فرض روی همه‌شان ۴۰۳ می‌گیرد. یعنی این حساب می‌تواند کاربر بسازد،
شاخص و قواعد نمره‌دهی را تنظیم کند و ماژول‌ها را روشن/خاموش کند، ولی نمرهٔ هیچ
کارمندی را نمی‌بیند و پای هیچ تأییدی نمی‌نشیند.

همان حساب همهٔ مجوزهای اداری را می‌گیرد، پس عملاً همان «سوپر ادمینی» است که
انتظار می‌رود: از داخل سامانه معاونت و مدیرعامل و مسئول واحد را می‌سازد، اسم
واقعی‌شان را می‌گذارد، و هر وقت لازم شد معاون دوم اضافه می‌کند. تفاوتش با یک
حسابِ همه‌کاره این است که «همه‌کاره بودن» این‌جا مجموعه‌ای از مجوزهای جداست که
می‌شود هرکدام را جداگانه پس گرفت — نه یک پرچمِ یکپارچه که برداشتنش یعنی هیچ.

رمز عبور از خط فرمان گرفته نمی‌شود: آرگومان‌ها در فهرست پروسه‌ها و تاریخچهٔ شل
دیده می‌شوند. یا تعاملی پرسیده می‌شود، یا از متغیر محیطی DBSPULSE_ADMIN_PASSWORD
خوانده می‌شود (برای اجرای خودکار).

اجرا (از پوشهٔ backend، با venv فعال)::

    python -m scripts.create_admin --username admin --full-name "مدیر سامانه، آقای رضایی"
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.capability import UserCapability
from app.models.enums import Capability, UserRole
from app.models.user import User

# همان حداقلی که app/schemas/user.py اعمال می‌کند. اگر این دو از هم دور بیفتند،
# اسکریپت حسابی می‌سازد که فرم ویرایش کاربر بعداً قبولش ندارد.
PASSWORD_MIN_LENGTH = 10

_PASSWORD_ENV = "DBSPULSE_ADMIN_PASSWORD"


def _read_password() -> str:
    from_env = os.environ.get(_PASSWORD_ENV)
    if from_env:
        return from_env
    if not sys.stdin.isatty():
        sys.exit(
            f"رمز عبور لازم است. یا این دستور را در ترمینال اجرا کنید، یا {_PASSWORD_ENV} را تنظیم کنید."
        )
    first = getpass.getpass("رمز عبور حساب مدیر: ")
    second = getpass.getpass("تکرار رمز عبور: ")
    if first != second:
        sys.exit("دو رمز یکسان نبودند.")
    return first


def main() -> int:
    parser = argparse.ArgumentParser(description="ساخت حساب مدیر سامانه")
    parser.add_argument("--username", required=True, help="نام کاربری برای ورود")
    parser.add_argument(
        "--full-name",
        required=True,
        help='نامی که در سامانه نشان داده می‌شود، مثل "مدیر سامانه، آقای رضایی"',
    )
    parser.add_argument(
        "--role",
        default=UserRole.support.value,
        choices=[r.value for r in UserRole],
        help="پیش‌فرض support: بیرون از زنجیرهٔ ارزیابی (توضیح بالای فایل)",
    )
    args = parser.parse_args()

    password = _read_password()
    if len(password) < PASSWORD_MIN_LENGTH:
        sys.exit(f"رمز عبور باید دست‌کم {PASSWORD_MIN_LENGTH} نویسه باشد.")

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == args.username)) is not None:
            sys.exit(f"کاربری با نام «{args.username}» از قبل وجود دارد.")

        user = User(
            username=args.username,
            full_name=args.full_name.strip() or None,
            password_hash=hash_password(password),
            role=UserRole(args.role),
            is_active=True,
            # رمز را خودِ همین شخص همین الان انتخاب کرده، پس اجبار به تغییر در
            # اولین ورود فقط یک مانع بی‌دلیل است. مسیر «HR برای دیگری رمز
            # می‌گذارد» جای دیگری است و آن‌جا این پرچم روشن می‌شود.
            must_change_password=False,
        )
        db.add(user)
        db.flush()

        for capability in Capability:
            db.add(UserCapability(user_id=user.id, capability=capability))
        db.commit()

        print(f"حساب «{args.username}» با نقش {args.role} و همهٔ مجوزهای اداری ساخته شد.")
        print("مجوزها: " + "، ".join(c.value for c in Capability))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
