"""login attempt lockout

P0-04 — شمارش تلاش‌های ناموفق ورود به ازای نام کاربری.

عمداً جدول است نه حافظهٔ پروسه: شمارندهٔ درون‌پروسه با چند replica به‌ازای هر کارگر
جدا شمرده می‌شود (یعنی محدودیت عملاً N برابر) و با هر ری‌استارت صفر می‌شود.

Revision ID: f2c60a8bd139
Revises: e4b8d03ca712
Create Date: 2026-08-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f2c60a8bd139'
down_revision: Union[str, None] = 'e4b8d03ca712'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("username", sa.String(length=150), primary_key=True),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "first_failed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_failed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    # جاروی پاک‌سازی روی last_failed_at فیلتر می‌کند؛ بدون ایندکس، با انباشته‌شدن
    # نام‌های کاربریِ تصادفیِ یک حملهٔ enumeration به scan کامل تبدیل می‌شود.
    op.create_index("ix_login_attempts_last_failed_at", "login_attempts", ["last_failed_at"])


def downgrade() -> None:
    op.drop_index("ix_login_attempts_last_failed_at", table_name="login_attempts")
    op.drop_table("login_attempts")
