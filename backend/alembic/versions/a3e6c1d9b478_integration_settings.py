"""تنظیمات ارسال بیرونی، قابل ویرایش از پنل

موتور ارسال (صف، تلاش مجدد، جداکردن خطای دائمی از گذرا) از قبل ساخته شده بود،
ولی هیچ جایی برای *وارد کردن* تنظیماتش نبود جز فایل `.env` روی سرور — یعنی
عوض‌کردن قالب پیامک به دسترسی SSH نیاز داشت.

این جدول فقط مقدارهای غیرمحرمانه را نگه می‌دارد. رمز SMTP و کلید API عمداً
این‌جا نمی‌آیند: چیزی که در دیتابیس بنشیند در هر بک‌آپی هم می‌نشیند، و بک‌آپ
دیتابیس معمولاً جاهایی می‌رود که `.env` نمی‌رود.

جدول خالی ساخته می‌شود و همین درست است: تا وقتی ردیفی نباشد، همان مقدارهای
`.env` اثر دارند و رفتار سامانه ذره‌ای عوض نمی‌شود.

Revision ID: a3e6c1d9b478
Revises: f7b3d5c8a294
Create Date: 2026-08-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3e6c1d9b478"
down_revision: str | None = "f7b3d5c8a294"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("integration_settings")
