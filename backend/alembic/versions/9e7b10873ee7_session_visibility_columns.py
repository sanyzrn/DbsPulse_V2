"""session visibility columns (P2-06)

سه ستون برای اینکه کاربر بتواند نشست‌های فعال خودش را *تشخیص* بدهد، نه فقط
بشمارد. «شما سه نشست فعال دارید» بی‌فایده است اگر معلوم نباشد کدام‌یک خودتانید.

نوشتنِ دستی، عمدی است. `alembic revision --autogenerate` روی این مخزن می‌خواست
تمام ایندکس‌ها و قیدهای یکتا را DROP کند — از جمله `uq_open_evaluation_per_personnel`
و `uq_single_open_period` که کل ایمنیِ هم‌زمانی این سامانه رویشان بنا شده — چون
آن‌ها در مایگریشن‌ها با op.create_index ساخته شده‌اند و روی مدل‌ها اعلام نشده‌اند،
پس autogenerate آن‌ها را «اضافی» می‌بیند. فقط همان چیزی که واقعاً عوض شده این‌جاست.

Revision ID: 9e7b10873ee7
Revises: e8f4b127d905
Create Date: 2026-08-14 13:51:29.669890
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9e7b10873ee7"
down_revision: str | None = "e8f4b127d905"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("auth_sessions", sa.Column("user_agent", sa.String(length=400), nullable=True))
    # ۴۵ نویسه: جا برای IPv6 کامل، شامل حالت نگاشت‌شدهٔ IPv4
    op.add_column("auth_sessions", sa.Column("ip", sa.String(length=45), nullable=True))
    op.add_column(
        "auth_sessions", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True)
    )
    # نشست‌های موجود «آخرین فعالیت» ندارند؛ زمان ساختشان نزدیک‌ترین حقیقتِ در دسترس
    # است و بهتر از خالی‌گذاشتن، که در UI به «هرگز» ترجمه می‌شد.
    op.execute("UPDATE auth_sessions SET last_used_at = created_at WHERE last_used_at IS NULL")


def downgrade() -> None:
    op.drop_column("auth_sessions", "last_used_at")
    op.drop_column("auth_sessions", "ip")
    op.drop_column("auth_sessions", "user_agent")
