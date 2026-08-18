"""جداکردن اختیارات مدیر سامانه از نقش منابع انسانی

دو مجوز تازه، که هرکدام چیزی را از هم جدا می‌کنند که تا امروز یکی بود:

* `manage_capabilities` از `manage_users` جدا شد. یکی‌بودنشان یعنی هرکس
  می‌توانست حساب بسازد، می‌توانست به خودش هم هر اختیاری بدهد — تفکیک وظایف با
  یک کلیک از بین می‌رفت. حالا «حساب می‌سازم» کارِ روزمرهٔ منابع انسانی است و
  «اختیار می‌دهم» نیست.
* `view_audit_log` از نقش `hr` جدا شد. دسترسی به کامل‌ترین ردِ تصمیم‌ها به کسی
  گره خورده بود که خودش در زنجیرهٔ تصمیم می‌ایستد، و گرفتنش از او هیچ راهی
  نداشت جز عوض‌کردن نقشش.

چرا دو مرحله
------------
مرحلهٔ اول همیشه اجرا می‌شود و فقط *حفظِ وضع موجود* است: هرکس امروز کاری را
می‌تواند بکند، فردا هم می‌تواند. بدون آن، ارتقا برای هر استقراری یک قطعیِ
بی‌خبر بود.

مرحلهٔ دوم تفکیک را واقعاً برقرار می‌کند و **فقط وقتی اجرا می‌شود که حساب مدیرِ
اختصاصی وجود داشته باشد** — یعنی یک حساب `support` فعال که مجوز اختیاردهی دارد.
بدون این شرط، مایگریشن می‌توانست سامانه‌ای را بی‌مدیر بگذارد که تنها راه خروجش
SQL دستی روی پروداکشن است. اگر شرط برقرار نباشد، هیچ‌چیز گرفته نمی‌شود و صفحهٔ
«مدیریت سامانه» همان هشدار همیشگی‌اش را نشان می‌دهد که تفکیک هنوز برقرار نیست.

Revision ID: e2c9a4b7f351
Revises: c4f8b2a17d63
Create Date: 2026-08-18
"""
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "e2c9a4b7f351"
down_revision: str | None = "c4f8b2a17d63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: نقش‌هایی که در زنجیرهٔ ارزیابی جایگاه دارند — همان‌هایی که نباید هم‌زمان
#: قواعد را بنویسند.
_CHAIN_ROLES = ("hr", "unit_supervisor", "deputy", "ceo")

#: اختیاراتی که به «مدیریت سامانه» تعلق دارند، نه به کارِ روزمرهٔ منابع انسانی.
#: `manage_users` و `manage_scoring` عمداً این‌جا نیستند: صفحهٔ «کاربران»،
#: «شاخص‌ها» و «طرح نمره‌دهی» بخشی از پنل منابع انسانی می‌مانند.
_ADMIN_ONLY = (
    "manage_capabilities",
    "manage_modules",
    "manage_integrations",
    "view_diagnostics",
    "view_audit_log",
)


def _add_enum_values(conn) -> None:
    # ALTER TYPE ... ADD VALUE داخل تراکنش اجرا نمی‌شود روی نسخه‌های قدیمی‌تر؛
    # IF NOT EXISTS اجرای دوباره را هم بی‌خطر می‌کند.
    for value in ("manage_capabilities", "view_audit_log"):
        conn.execute(text(f"ALTER TYPE capability ADD VALUE IF NOT EXISTS '{value}'"))


def upgrade() -> None:
    conn = op.get_bind()
    _add_enum_values(conn)
    # مقادیر تازهٔ enum تا پایان همین تراکنش قابل *استفاده* نیستند.
    conn.execute(text("COMMIT"))

    # ── مرحلهٔ ۱: حفظ وضع موجود ──────────────────────────────────────────
    # هرکس امروز می‌تواند مجوز بدهد، فردا هم می‌تواند.
    conn.execute(
        text(
            "INSERT INTO user_capabilities (user_id, capability) "
            "SELECT user_id, 'manage_capabilities' FROM user_capabilities "
            "WHERE capability = 'manage_users' "
            "ON CONFLICT (user_id, capability) DO NOTHING"
        )
    )
    # و هرکس امروز لاگ کامل را می‌بیند (نقش hr)، فردا هم می‌بیند.
    conn.execute(
        text(
            "INSERT INTO user_capabilities (user_id, capability) "
            "SELECT id, 'view_audit_log' FROM users WHERE role = 'hr' "
            "ON CONFLICT (user_id, capability) DO NOTHING"
        )
    )

    # ── مرحلهٔ ۲: تفکیک، فقط اگر جایگزینی هست ─────────────────────────────
    dedicated_admin = conn.execute(
        text(
            "SELECT 1 FROM users u JOIN user_capabilities c ON c.user_id = u.id "
            "WHERE u.role = 'support' AND u.is_active AND c.capability = 'manage_capabilities' "
            "LIMIT 1"
        )
    ).scalar()
    if dedicated_admin is None:
        return

    # اول دادن، بعد گرفتن — و ترتیبش مهم است. اگر اول از زنجیره گرفته می‌شد،
    # لحظه‌ای وجود داشت که هیچ‌کس لاگ را نمی‌دید؛ و اگر دادن فراموش می‌شد، آن
    # لحظه دائمی می‌شد. لاگی که هیچ‌کس نمی‌تواند بخواند، از نبودنش بدتر است:
    # به‌نظر می‌رسد پاسخ‌گویی برقرار است.
    # حلقه به‌جای آرایه: `text()` رشتهٔ `:param::type` را درست تفسیر نمی‌کند و
    # کست به نوعِ enum این‌جا لازم است. شش دستور کوچک، خواناتر از یک دستور با
    # سه لایه کست.
    for capability in _ADMIN_ONLY:
        conn.execute(
            text(
                "INSERT INTO user_capabilities (user_id, capability) "
                "SELECT id, :capability FROM users "
                "WHERE role = 'support' AND is_active "
                "ON CONFLICT (user_id, capability) DO NOTHING"
            ),
            {"capability": capability},
        )

    for capability in _ADMIN_ONLY:
        conn.execute(
            text(
                "DELETE FROM user_capabilities WHERE capability = :capability "
                "AND user_id IN (SELECT id FROM users WHERE role = ANY(:chain_roles))"
            ),
            {"capability": capability, "chain_roles": list(_CHAIN_ROLES)},
        )


def downgrade() -> None:
    # مقادیر enum برگردانده نمی‌شوند: PostgreSQL حذف مقدار از یک enum را
    # پشتیبانی نمی‌کند، و ردیف‌هایی که به آن‌ها اشاره دارند همین حالا پاک می‌شوند.
    conn = op.get_bind()
    conn.execute(
        text("DELETE FROM user_capabilities WHERE capability IN ('manage_capabilities', 'view_audit_log')")
    )
