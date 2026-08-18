"""پاک‌کردن کاملِ دادهٔ سامانه و ساختن دوبارهٔ ساختار از روی مایگریشن‌ها.

چرا «حذف کارمندهای تست» کار دیگری نیست
--------------------------------------
حدس طبیعی این است که یک اسکریپت بنویسیم که پرسنل نمونه را DELETE کند. روی این
دیتابیس آن اسکریپت نوشتنی نیست، و دلیلش هم اتفاقی نیست:

* `audit_log` عمداً فقط-افزودنی است. تریگر `trg_audit_log_append_only`
  (مایگریشن e8f4b127d905) هر UPDATE و DELETE را رد می‌کند، و ردیف‌ها با زنجیرهٔ
  هش به هم بسته‌اند تا دست‌کاری قابل‌کشف باشد.
* `audit_log.evaluation_record_id` با ON DELETE NO ACTION به ارزیابی‌ها وصل است،
  و `evaluation_access.personnel_id` به پرسنل. پس تا وقتی ردیف حسابرسی هست،
  ارزیابیِ مربوط به آن پاک نمی‌شود؛ و تا وقتی ارزیابی هست، پرسنلش پاک نمی‌شود.

یعنی «پرسنلی که یک بار ارزیابی شده» به‌طور طراحی‌شده حذف‌نشدنی است. تنها راهی
که این را دور می‌زند، خاموش‌کردن همان تریگری است که کل تمپر-اویدنت بودن لاگ به
آن بند است — و آن کار، خرابیِ چیزی است که این سامانه ادعایش را دارد.

پس راهِ درستِ «از صفر شروع کنم» این است: کل schema دور ریخته شود و مایگریشن‌ها
از نو اجرا شوند. با `SEED_DEMO_DATA=false` هیچ داده و هیچ حسابِ نمونه‌ای ساخته
نمی‌شود؛ اولین حساب واقعی را با `scripts.create_admin` بسازید.

اجرا (از پوشهٔ backend، با venv فعال)::

    set SEED_DEMO_DATA=false
    python -m scripts.reset_database --yes
    python -m scripts.create_admin --username admin --full-name "مدیر سامانه، آقای ..."
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal, engine

BACKEND_DIR = Path(__file__).resolve().parent.parent

# جدول‌هایی که شمردنشان به کاربر می‌گوید دقیقاً چه چیزی را دارد از دست می‌دهد.
_COUNTED = ("personnel", "users", "evaluation_records", "audit_log")


def _summary() -> list[tuple[str, int]]:
    rows = []
    with SessionLocal() as db:
        for table in _COUNTED:
            try:
                rows.append((table, db.scalar(text(f"SELECT count(*) FROM {table}")) or 0))
            except Exception:  # noqa: BLE001 - جدول هنوز ساخته نشده؛ صفر یعنی همان
                db.rollback()
                rows.append((table, 0))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="پاک‌کردن کامل داده و ساخت دوبارهٔ ساختار")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="بدون این، فقط گزارش می‌دهد چه چیزی پاک می‌شود و کاری نمی‌کند",
    )
    args = parser.parse_args()

    if settings.environment == "production":
        sys.exit("روی production اجرا نمی‌شود. این اسکریپت کل داده را پاک می‌کند.")

    print(f"دیتابیس: {engine.url.render_as_string(hide_password=True)}")
    for table, count in _summary():
        print(f"    {table:20} {count}")

    if not args.yes:
        print("\nهیچ تغییری داده نشد. برای اجرای واقعی، دوباره با --yes بزنید.")
        return 0

    # DROP SCHEMA به‌جای حذف ردیف‌به‌ردیف: هم تریگر فقط-افزودنی را دور نمی‌زند
    # (کل جدول می‌رود، نه بعضی ردیف‌هایش)، هم alembic_version را پاک می‌کند تا
    # مایگریشن‌ها واقعاً از صفر اجرا شوند.
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()
    print("\nschema پاک و از نو ساخته شد. اجرای مایگریشن‌ها...")

    result = subprocess.run(["alembic", "upgrade", "head"], cwd=BACKEND_DIR)
    if result.returncode != 0:
        sys.exit("مایگریشن‌ها با خطا تمام شدند — خروجی بالا را ببینید.")

    print("\nدیتابیس خالی و آمادهٔ استفاده است.")
    if settings.seed_demo_data:
        print("توجه: SEED_DEMO_DATA=true بود، پس حساب‌ها و پرسنل نمونه دوباره ساخته شدند.")
    else:
        print("هیچ حسابی وجود ندارد. اولین حساب را بسازید:")
        print('    python -m scripts.create_admin --username admin --full-name "مدیر سامانه"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
