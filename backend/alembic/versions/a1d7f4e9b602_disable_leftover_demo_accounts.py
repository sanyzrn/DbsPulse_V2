"""disable leftover demo accounts

هر محیطی که پیش از فلگ‌دار شدن مایگریشن seed (1eaa459f4dde) مایگریشن خورده باشد،
پنج کاربر دمو با رمز مشترکِ منتشرشده دارد. گیت‌کردن آن مایگریشن فقط جلوی محیط‌های
*جدید* را می‌گیرد؛ این مایگریشن محیط‌های موجود را هم می‌بندد.

فقط حساب‌هایی بسته می‌شوند که رمزشان واقعاً هنوز همان رمز دموست — اگر کسی رمز hr1
را عوض کرده باشد، آن حساب دست‌نخورده می‌ماند.

Revision ID: a1d7f4e9b602
Revises: d5b1f3e7c920
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

from app.core.config import settings
from app.core.demo_data import DEMO_PASSWORD, DEMO_USERNAMES
from app.core.security import verify_password

# revision identifiers, used by Alembic.
revision: str = 'a1d7f4e9b602'
down_revision: Union[str, None] = 'd5b1f3e7c920'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # در محیط دمو/توسعه‌ای که صراحتاً SEED_DEMO_DATA=true دارد، این حساب‌ها عمداً
    # وجود دارند و کاربردشان همین است — نمی‌بندیمشان.
    if settings.seed_demo_data:
        return

    conn = op.get_bind()
    rows = conn.execute(
        text(
            "SELECT id, password_hash FROM users "
            "WHERE username = ANY(:usernames) AND is_active = true"
        ),
        {"usernames": list(DEMO_USERNAMES)},
    ).all()

    stale_ids = [row.id for row in rows if verify_password(DEMO_PASSWORD, row.password_hash)]
    if not stale_ids:
        return

    # token_version را هم بالا می‌بریم تا هر access/refresh token صادرشده برای این
    # حساب‌ها همین حالا باطل شود، نه فقط ورودهای بعدی.
    conn.execute(
        text(
            "UPDATE users SET is_active = false, must_change_password = true, "
            "token_version = token_version + 1 WHERE id = ANY(:ids)"
        ),
        {"ids": stale_ids},
    )


def downgrade() -> None:
    # عمداً no-op: برگرداندن این مایگریشن یعنی «حساب با رمز عمومی را دوباره فعال کن»،
    # که یک عقبگرد امنیتی است نه بازگردانی حالت. اگر واقعاً حساب دمو لازم دارید،
    # SEED_DEMO_DATA را روشن کنید یا با CLI کاربر بسازید.
    pass
