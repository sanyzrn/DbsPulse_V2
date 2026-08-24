"""امتیاز ویژه: نمرهٔ اختیاری بابت کار خارج از شرح وظایف

فرم ارزیابی به شاخص‌های ثابتی نمره می‌دهد و همین درست است — مقایسه‌پذیری از
همان‌جا می‌آید. ولی کاری که در هیچ شاخصی نمی‌گنجد هم واقعی است: کارمندی که
پروژه‌ای بیرون از شرح وظایفش را جلو می‌برد، تا امروز جایی برای دیده‌شدن نداشت
و ارزیاب یا نادیده‌اش می‌گرفت یا — بدتر — نمرهٔ یک شاخصِ بی‌ربط را بالا می‌برد
تا جبرانش کند. یعنی نبودِ این ستون، دادهٔ شاخص‌ها را هم آلوده می‌کرد.

سه ستون اضافه می‌شود:

* `evaluation_records.bonus_points` — امتیاز ویژهٔ ثبت‌شده (NULL و صفر هم‌معنا).
* `evaluation_records.bonus_reason` — دلیلش؛ در سطح دیتابیس اجباری است وقتی
  امتیازی داده شده باشد. عددی که کسی نتواند توضیحش را بخواند، در سندی که مبنای
  تصمیم تمدید قرارداد است قابل دفاع نیست.
* `evaluation_records.base_weighted_pct` — امتیازِ فرم پیش از افزودن امتیاز
  ویژه. مشتق‌کردنش از تفریق کافی نبود: وقتی جمع از ۱۰۰ بگذرد، امتیاز اضافه‌شده
  کوتاه می‌شود و آن تفریق عددی می‌داد که هرگز محاسبه نشده بود.

و یک ستون روی طرح نمره‌دهی: `scoring_schemes.bonus_max_points`. سقف، مثل بقیهٔ
قواعد، نسخه‌دار است (P1-04) تا هر پرونده با سقفِ نسخهٔ خودش سنجیده شود؛ ۵ برای
نسخه‌های موجود همان پیش‌فرضِ ثابت‌های کد است.

پرونده‌های گذشته دست‌نخورده می‌مانند: هر سه ستون NULL می‌شوند، یعنی «امتیاز
ویژه‌ای در کار نبود» — که دقیقاً درست است.

Revision ID: d5a91f37c2e8
Revises: b8d2f6a41c93
Create Date: 2026-08-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5a91f37c2e8"
down_revision: str | None = "b8d2f6a41c93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evaluation_records", sa.Column("bonus_points", sa.Numeric(4, 2), nullable=True)
    )
    op.add_column("evaluation_records", sa.Column("bonus_reason", sa.String(500), nullable=True))
    op.add_column(
        "evaluation_records", sa.Column("base_weighted_pct", sa.Numeric(5, 2), nullable=True)
    )
    op.create_check_constraint(
        "ck_evaluation_records_bonus_not_negative",
        "evaluation_records",
        "bonus_points IS NULL OR bonus_points >= 0",
    )
    op.create_check_constraint(
        "ck_evaluation_records_bonus_needs_reason",
        "evaluation_records",
        "bonus_points IS NULL OR bonus_points = 0 OR bonus_reason IS NOT NULL",
    )

    # server_default می‌ماند: ستون NOT NULL است و ردیف‌های موجود باید مقداری
    # بگیرند. برداشتنش پس از پرکردن، تنها راهِ درج طرح تازه را از مسیر کدی
    # می‌کرد که مقدار را صریح می‌دهد — و اسکریپت‌های seed این را نمی‌دانند.
    op.add_column(
        "scoring_schemes",
        sa.Column("bonus_max_points", sa.Numeric(4, 2), nullable=False, server_default="5"),
    )


def downgrade() -> None:
    op.drop_column("scoring_schemes", "bonus_max_points")
    op.drop_constraint("ck_evaluation_records_bonus_needs_reason", "evaluation_records")
    op.drop_constraint("ck_evaluation_records_bonus_not_negative", "evaluation_records")
    op.drop_column("evaluation_records", "base_weighted_pct")
    op.drop_column("evaluation_records", "bonus_reason")
    op.drop_column("evaluation_records", "bonus_points")
