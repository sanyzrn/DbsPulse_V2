"""صندلیِ تکراری در زنجیرهٔ ارزیابی

گزارش ممیزیِ HR ایراد گرفت که سه مرحلهٔ زنجیره هیچ‌جا «سه نفر متفاوت» بودنشان
سنجیده نمی‌شود، و درست هم بود: `may_act_at` عمداً اجازه می‌دهد مافوق در مرحلهٔ
پایین‌تر بنشیند، پس یک نفر می‌تواند دو صندلی داشته باشد و لاگ ممیزی *دو تأیید*
نشان بدهد — دو رویداد، دو مُهر، یک آدم.

ولی «هر سه باید متفاوت باشند» پاسخ درستی نیست، چون یکی از این سه ترکیب اصلاً
تکراری نیست: **کسی که مستقیماً زیر نظر مدیرعامل کار می‌کند.** مدیرعامل هم
نمره‌دهندهٔ اولش است و هم تأییدکنندهٔ نهایی، و بالای سرش کسِ دیگری *وجود ندارد*.
ممنوع‌کردنش یعنی آن افراد قابل ثبت نیستند — همان اشتباهی که یک بار با ستون
NOT NULL معاونت مرتکب شدیم و آدم‌ها را وادار کرد معاونتِ ساختگی بنویسند.

پس تفکیک بر اساس این‌که آیا صندلیِ تکراری *بیانِ دیگری* دارد یا نه:

* «مسئول واحد = معاونت» → تکراری است؛ شکل درستش خالی‌گذاشتنِ مسئول واحد است
  (مسیر «مدیر»: معاونت خودش نمره‌دهندهٔ اول می‌شود). **ممنوع.**
* «معاونت = مدیرعامل» → تکراری است؛ شکل درستش خالی‌گذاشتنِ معاونت است (پرونده از
  منابع انسانی مستقیم به مدیرعامل می‌رود). **ممنوع.**
* «مسئول واحد = مدیرعامل» → بیان دیگری ندارد؛ تنها راه ثبتِ کسی است که مستقیم
  زیر نظر مدیرعامل است. **مجاز، ولی افشا می‌شود** — سند نهایی صریحاً می‌گوید
  نمره‌دهندهٔ اول و تأییدکنندهٔ نهایی یک نفر بوده‌اند، تا آن دو تأیید در لاگ،
  چیزی را ادعا نکنند که رخ نداده.

## چرا NOT VALID

قیدها با `NOT VALID` اضافه می‌شوند: از این پس هر درج و هر به‌روزرسانی سنجیده
می‌شود، ولی ردیف‌های موجود اعتبارسنجی نمی‌شوند.

این سهل‌انگاری نیست، تصمیم است. اگر قید معمولی می‌بود و نصبی از قبل یک زنجیرهٔ
تکراری داشت، *همین مایگریشن* شکست می‌خورد و کل ارتقا متوقف می‌شد — یعنی یک دادهٔ
اشتباهِ قابل‌اصلاح به یک سامانهٔ بالا‌نیامده ترجمه می‌شد. با NOT VALID مسیر اصلاح
باز است و بسته‌شدنِ درِ ورودی هم فوری. ردیف‌های ناسازگارِ موجود در همان خروجی
ارتقا فهرست می‌شوند.

روی `evaluation_records` هم اعمال می‌شود، نه فقط روی جدول تنظیمات: پرونده زنجیره
را در لحظهٔ ساخت *کپی* می‌کند و `reassign` هم مستقیم روی همان می‌نویسد.

Revision ID: e9c47b3f1a52
Revises: d5a91f37c2e8
Create Date: 2026-08-24
"""
import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger("alembic.runtime.migration")

revision: str = "e9c47b3f1a52"
down_revision: str | None = "d5a91f37c2e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: مرحلهٔ خالی شمرده نمی‌شود؛ نبودنِ مسئول واحد یا معاونت خودش حالتی مجاز است
#: (مسیر «مدیر»، و زنجیرهٔ بی‌معاونت).
#: «مسئول واحد = مدیرعامل» عمداً این‌جا نیست — توضیحش بالا.
_CHECKS = [
    (
        "ck_{table}_supervisor_not_deputy",
        "unit_supervisor_user_id IS NULL OR deputy_user_id IS NULL "
        "OR unit_supervisor_user_id <> deputy_user_id",
    ),
    (
        "ck_{table}_deputy_not_ceo",
        "deputy_user_id IS NULL OR deputy_user_id <> ceo_user_id",
    ),
]

_TABLES = ("evaluation_access", "evaluation_records")


def _warn_about_existing_violations() -> None:
    """ردیف‌های ناسازگارِ موجود را می‌شمارد و اسمشان را می‌گوید.

    NOT VALID یعنی این مایگریشن به‌خاطرشان شکست نمی‌خورد — که درست است — ولی
    سکوت دربارهٔ آن‌ها یعنی کسی هرگز خبردار نمی‌شود. این هشدار در همان خروجی
    ارتقا دیده می‌شود؛ خواندنش برای کسی که ارتقا را اجرا می‌کند اجتناب‌ناپذیر است.
    """
    rows = op.get_bind().execute(
        sa.text(
            """
            SELECT p.personnel_code, p.full_name
            FROM evaluation_access a
            JOIN personnel p ON p.id = a.personnel_id
            WHERE a.unit_supervisor_user_id = a.deputy_user_id
               OR a.deputy_user_id = a.ceo_user_id
            ORDER BY p.personnel_code
            """
        )
    ).all()
    if not rows:
        return
    listed = "، ".join(f"{code} ({name})" for code, name in rows[:20])
    logger.warning(
        "زنجیرهٔ ارزیابیِ %d پرسنل صندلیِ تکراری دارد و باید در پنل اصلاح شود "
        "(مرحلهٔ تکراری را خالی بگذارید): %s%s",
        len(rows),
        listed,
        " …" if len(rows) > 20 else "",
    )


def upgrade() -> None:
    _warn_about_existing_violations()
    for table in _TABLES:
        for name_template, condition in _CHECKS:
            name = name_template.format(table=table)
            op.execute(
                f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({condition}) NOT VALID"
            )


def downgrade() -> None:
    for table in _TABLES:
        for name_template, _ in _CHECKS:
            name = name_template.format(table=table)
            op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")
