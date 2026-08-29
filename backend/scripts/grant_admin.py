"""بازگرداندنِ اختیارات اداری به یک حسابِ *موجود*.

چرا این فایل هست
----------------
مایگریشن `f2a7d3c9e861` برای هر حسابِ دارای نقش `hr` فقط سه مجوزِ پایه را نگه
داشت و بقیه را پاک کرد. روی نصبی که مدیرش نقش `hr` داشت — یعنی هر نصبی که پیش
از افزوده‌شدنِ حساب bootstrap راه افتاده بود — نتیجه این شد که همان حساب دیگر
«مدیریت سامانه» را نمی‌دید. `downgrade` آن مایگریشن هم عمداً خالی است، پس
مقدارهای قبلی از خودِ دیتابیس قابل بازسازی نیستند.

`ensure_bootstrap_admin` در بالا آمدنِ بعدی این بن‌بست را می‌شکند، ولی با ساختنِ
یک حسابِ *تازه* که رمزش یک‌بار در لاگ می‌آید. وقتی می‌دانید کدام حساب باید مدیر
باشد، این اسکریپت مسیر مستقیم‌تری است: همان حساب، بدون حسابِ اضافه.

چرا اسکریپت و نه مایگریشن
--------------------------
انتخابِ اینکه *کدام* حساب باید اختیاردهنده باشد یک تصمیم امنیتی است و دیتابیس
جواب مطمئنی برایش ندارد. مایگریشنی که خودش حدس بزند، ممکن است حسابی را بالا
ببرد که نباید. این‌جا نام حساب را شما می‌دهید.

اجرا (از پوشهٔ backend، با venv فعال)::

    python -m scripts.grant_admin --username admin
    python -m scripts.grant_admin --username admin --only manage_capabilities manage_ai
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.capability import UserCapability
from app.models.enums import Capability
from app.models.user import User
from app.services.audit import log_event
from app.services.authorization import capabilities_of


def main() -> int:
    parser = argparse.ArgumentParser(description="بازگرداندن اختیارات اداری به یک حساب موجود")
    parser.add_argument("--username", required=True, help="نام کاربریِ حسابِ هدف")
    parser.add_argument(
        "--only",
        nargs="*",
        metavar="CAPABILITY",
        help="فقط همین مجوزها. بدون آن، همهٔ اختیارات اداری داده می‌شود.",
    )
    args = parser.parse_args()

    if args.only:
        unknown = [name for name in args.only if name not in Capability.__members__]
        if unknown:
            sys.exit(f"مجوز ناشناخته: {'، '.join(unknown)}")
        wanted = {Capability[name] for name in args.only}
    else:
        wanted = set(Capability)

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == args.username))
        if user is None:
            sys.exit(f"کاربری با نام «{args.username}» پیدا نشد.")
        if not user.is_active:
            sys.exit(
                f"حساب «{args.username}» غیرفعال است. اول از صفحهٔ «مدیریت حساب» فعالش کنید — "
                "مجوز دادن به حسابی که نمی‌تواند وارد شود کاری از پیش نمی‌برد."
            )

        added = sorted(wanted - capabilities_of(db, user.id), key=lambda c: c.value)
        if not added:
            print(f"حساب «{args.username}» همهٔ این مجوزها را از قبل دارد؛ چیزی عوض نشد.")
            return 0

        for capability in added:
            db.add(UserCapability(user_id=user.id, capability=capability))
        # همان چیزی که مایگریشن نکرد: ردِ این تغییر در زنجیرهٔ ممیزی می‌ماند.
        # actor خودِ همین حساب است چون این کار از خط فرمان انجام شده، نه از پنل.
        log_event(
            db,
            actor_user_id=user.id,
            event_type="capabilities_granted",
            new_value={
                "user_id": user.id,
                "username": user.username,
                "capabilities": [c.value for c in added],
                "via": "scripts.grant_admin",
            },
        )
        db.commit()

        print(f"به حساب «{args.username}» داده شد: " + "، ".join(c.value for c in added))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
