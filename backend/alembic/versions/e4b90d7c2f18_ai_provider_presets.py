"""سرویس‌های آمادهٔ دستیار

تا امروز مدیر باید آدرس سرویس را از حفظ می‌نوشت، و نیمی از مشکلات راه‌اندازی
همان یک `/v1` جامانده بود. حالا فهرستی از سرویس‌های آماده هست و این ستون فقط
می‌گوید کدامشان انتخاب شده — آدرس و مدل همان‌جا که بودند می‌مانند.

مقدار پیش‌فرض «custom» است تا نصبی که آدرس را دستی نوشته، همان‌طور بماند.

Revision ID: e4b90d7c2f18
Revises: c1a5e70bd932
Create Date: 2026-08-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4b90d7c2f18"
down_revision: str | None = "c1a5e70bd932"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_settings",
        sa.Column("provider", sa.String(length=40), server_default="custom", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("ai_settings", "provider")
