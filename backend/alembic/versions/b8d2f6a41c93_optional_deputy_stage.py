"""معاونت می‌تواند در زنجیره نباشد

از ساختار واقعی یک سازمان آمد: در فایل پرسنلی که وارد شد، ۹ نفر هیچ معاونتی
بالای سرشان نداشتند و مستقیم زیر نظر مدیرعامل بودند. ستون NOT NULL بود، یعنی
تنها راه ثبتشان گذاشتن یک معاونتِ ساختگی بالای سرشان بود — و همان نام ساختگی
بعداً پای تأیید پروندهٔ آن‌ها می‌نشست، در سندی که امضا می‌شود.

قرینهٔ چیزی است که از قبل برای سرِ دیگر زنجیره وجود داشت: مسئول واحدِ خالی یعنی
مسیر «مدیر»، و معاونت خودش نمره‌دهندهٔ اول است. حالا معاونتِ خالی هم یعنی پرونده
از منابع انسانی مستقیم به مدیرعامل می‌رود.

هر دو با هم خالی نمی‌شوند: گارد روتر جلویش را می‌گیرد، چون آن‌وقت هیچ‌کس
نمره‌دهنده نیست و پرونده از همان اول در حالتی می‌ماند که فقط لغو از آن خارجش
می‌کند.

هیچ داده‌ای عوض نمی‌شود؛ فقط قید برداشته می‌شود. ردیف‌های موجود همگی معاونت
دارند و همان‌طور می‌مانند.

Revision ID: b8d2f6a41c93
Revises: a3e6c1d9b478
Create Date: 2026-08-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8d2f6a41c93"
down_revision: str | None = "a3e6c1d9b478"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("evaluation_access", "deputy_user_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column(
        "evaluation_records", "deputy_user_id", existing_type=sa.Integer(), nullable=True
    )


def downgrade() -> None:
    # برگرداندن قید روی داده‌ای که ممکن است NULL داشته باشد شکست می‌خورد، و همین
    # درست است: بازگشت باید صریح باشد، نه اینکه ردیف‌ها را بی‌صدا دور بریزد.
    op.alter_column(
        "evaluation_records", "deputy_user_id", existing_type=sa.Integer(), nullable=False
    )
    op.alter_column(
        "evaluation_access", "deputy_user_id", existing_type=sa.Integer(), nullable=False
    )
