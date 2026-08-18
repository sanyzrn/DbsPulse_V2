"""ثبت خروج پرسنل از سازمان

«غیرفعال» به‌تنهایی نمی‌گفت چه اتفاقی افتاده. استعفا، اخراج، پایان قرارداد و
بازنشستگی در هیچ گزارش منابع انسانی‌ای یک چیز نیستند: نرخ استعفا در یک واحد یک
سیگنال است، پایان قرارداد یک برنامه‌ریزی. بدون ثبت علت، هر دو به یک ردیفِ
خاموشِ یکسان تبدیل می‌شدند.

تاریخ خروج جدا از `contract_end_date` است و این عمدی است: تاریخ پایان قرارداد یک
*برنامه* است که ممکن است هرگز اتفاق نیفتد (تمدید می‌شود)، و تاریخ خروج یک
*واقعه*. یکی‌کردنشان یعنی نشود گفت چند نفر پیش از پایان قراردادشان رفتند.

هر دو ستون خالی‌پذیرند: برای پرسنلِ غیرفعالِ موجود هیچ علتی در داده نیست و
ساختنش جعل است. همان‌ها خالی می‌مانند تا کسی که می‌داند پرشان کند.

Revision ID: f7b3d5c8a294
Revises: e2c9a4b7f351
Create Date: 2026-08-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7b3d5c8a294"
down_revision: str | None = "e2c9a4b7f351"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REASONS = ("resignation", "dismissal", "contract_end", "retirement", "other")


def upgrade() -> None:
    separation_reason = sa.Enum(*_REASONS, name="separation_reason")
    separation_reason.create(op.get_bind(), checkfirst=True)
    op.add_column("personnel", sa.Column("separation_date", sa.Date(), nullable=True))
    op.add_column(
        "personnel",
        sa.Column("separation_reason", separation_reason, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("personnel", "separation_reason")
    op.drop_column("personnel", "separation_date")
    sa.Enum(name="separation_reason").drop(op.get_bind(), checkfirst=True)
