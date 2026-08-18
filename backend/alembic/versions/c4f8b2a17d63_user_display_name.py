"""نام قابل‌نمایش برای حساب‌های کاربری

حساب‌های نقش‌دار — معاونت، مدیرعامل، مسئول واحد، منابع انسانی — پروندهٔ پرسنلی
ندارند، پس تا امروز همه‌جای سامانه با نام کاربری دیده می‌شدند: «dep1» به‌جای نام
کسی که پای تأیید یک ارزیابی ایستاده. نام کاربری برای *ورود* است؛ برای شناساندن
یک آدم به آدم دیگر ساخته نشده.

ستون خالی‌پذیر است، چون هیچ نامی برای حساب‌های موجود نمی‌شود از روی داده حدس زد
و ساختنش هم درست نیست. تا وقتی پر نشود، `User.display_name` همان نام کاربری را
برمی‌گرداند — یعنی هیچ صفحه‌ای خالی نمی‌شود.

تنها استثنا حساب‌های دموست: آن‌ها آدم واقعی نیستند و نامِ توصیفی گرفتن‌شان چیزی
را جعل نمی‌کند، ولی نمایش سامانه را از «dep1» به چیزی خوانا می‌برد. این کار فقط
وقتی انجام می‌شود که SEED_DEMO_DATA=true باشد و رمز حساب هنوز همان رمز عمومی دمو
باشد — یعنی حسابی که واقعاً هنوز یک حساب نمونه است و کسی تحویلش نگرفته.

Revision ID: c4f8b2a17d63
Revises: b7d4e2a91c68
Create Date: 2026-08-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

from app.core.config import settings
from app.core.demo_data import DEMO_PASSWORD
from app.core.security import verify_password

revision: str = "c4f8b2a17d63"
down_revision: str | None = "b7d4e2a91c68"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# نام‌ها عمداً «سِمَت + نمونه» هستند و نه اسم آدم. یک نام جعلیِ باورپذیر روی یک
# حساب نمونه، همان چیزی است که بعداً کسی آن را واقعی فرض می‌کند.
_DEMO_LABELS = {
    "hr1": "منابع انسانی (حساب نمونه)",
    "sup1": "مسئول واحد ۱ (حساب نمونه)",
    "sup2": "مسئول واحد ۲ (حساب نمونه)",
    "dep1": "معاونت (حساب نمونه)",
    "ceo1": "مدیرعامل (حساب نمونه)",
}


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(length=200), nullable=True))

    if not settings.seed_demo_data:
        return

    conn = op.get_bind()
    rows = conn.execute(
        text(
            "SELECT id, username, password_hash FROM users "
            "WHERE username = ANY(:usernames) AND full_name IS NULL"
        ),
        {"usernames": list(_DEMO_LABELS)},
    ).all()
    for user_id, username, password_hash in rows:
        # اگر کسی رمز را عوض کرده، حساب دیگر «نمونه» نیست و اسم‌گذاری روی آن
        # کارِ ما نیست.
        if not verify_password(DEMO_PASSWORD, password_hash):
            continue
        conn.execute(
            text("UPDATE users SET full_name = :full_name WHERE id = :id"),
            {"full_name": _DEMO_LABELS[username], "id": user_id},
        )


def downgrade() -> None:
    op.drop_column("users", "full_name")
