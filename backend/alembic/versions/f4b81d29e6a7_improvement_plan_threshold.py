"""واجد بودنِ برنامهٔ بهبود، با عدد نه با برچسب

تا امروز واجد بودن با مقایسهٔ *رشتهٔ* نتیجه سنجیده می‌شد و فقط یک برچسب را
می‌پذیرفت: «تمدید مشروط به برنامه بهبود مکتوب». دو خرابی داشت.

**اول:** نتایج زیر ۶۰٪ — بدترین عملکردها، همان‌هایی که پیش از قطع همکاری بیشتر
از همه به سابقهٔ مکتوب نیاز دارند — هیچ مسیر مستندسازی نداشتند. معکوسِ چیزی که
باید باشد.

**دوم، و خاموش‌تر:** برچسب‌ها از P1-04 به بعد در خودِ طرح نمره‌دهی تعریف
می‌شوند. سازمانی که برچسب خودش را می‌نوشت، آن مقایسهٔ رشته‌ای هیچ‌وقت جواب
نمی‌داد و برنامهٔ بهبود بی‌صدا برای *هیچ‌کس* فعال نمی‌شد — بدون هیچ خطایی.

پس سنجش با عدد: هر پروندهٔ نهایی‌شده‌ای که امتیازش زیر این سقف باشد واجد است. سقف
هم مثل بقیهٔ قواعد نسخه‌دار است، و ۷۵ برای نسخه‌های موجود دقیقاً همان مرزِ
«تمدید مشروط» در ثابت‌های کد است — یعنی رفتار برای بازهٔ فعلی عوض نمی‌شود، فقط
بازهٔ پایین‌تر هم اضافه می‌شود.

Revision ID: f4b81d29e6a7
Revises: e9c47b3f1a52
Create Date: 2026-08-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4b81d29e6a7"
down_revision: str | None = "e9c47b3f1a52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scoring_schemes",
        sa.Column(
            "improvement_plan_max_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="75",
        ),
    )


def downgrade() -> None:
    op.drop_column("scoring_schemes", "improvement_plan_max_pct")
