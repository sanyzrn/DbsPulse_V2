"""دعوت به خودارزیابی

خودارزیابی از قبل وجود داشت و اختیاری بود. ولی «اختیاری» با «کسی خبرش نکرده»
یکی نیست: تا امروز کارمند فقط اگر خودش وارد سامانه می‌شد و پروندهٔ بازش را پیدا
می‌کرد می‌فهمید که می‌تواند نظرش را ثبت کند — و عملاً تقریباً هیچ‌کس نمی‌فهمید.

دو ستون تازه روی *پرونده* می‌نشینند و نه روی پرسنل: دعوت مربوط به همین دورهٔ
ارزیابی است و دورهٔ بعد باید دوباره فرستاده شود.

اصل

Revision ID: 35ea3c955ab3
Revises: ddafefc08701
Create Date: 2026-08-25 19:50:05.758139

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "35ea3c955ab3"
down_revision: str | None = "ddafefc08701"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evaluation_records",
        sa.Column("self_assessment_invited_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "evaluation_records",
        sa.Column("self_assessment_invited_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_evaluation_records_self_assessment_invited_by",
        "evaluation_records",
        "users",
        ["self_assessment_invited_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_evaluation_records_self_assessment_invited_by",
        "evaluation_records",
        type_="foreignkey",
    )
    op.drop_column("evaluation_records", "self_assessment_invited_by_user_id")
    op.drop_column("evaluation_records", "self_assessment_invited_at")
