"""تمدیدِ مهلتِ ثبت برای یک پروندهٔ مشخص

مهلتِ عادی از `evaluation_periods.ends_on` می‌آید و برای همه یکی است. این چهار
ستون استثنایی را ثبت می‌کنند که منابع انسانی برای یک پرونده می‌دهد — و چون
تاریخ‌دار است، خودش بسته می‌شود.

قاعدهٔ ترکیبِ این تاریخ با مهلتِ دوره در `services/evaluation_window.py` است.

Revision ID: b3e9d1f47a52
Revises: a4f6c8e91b20
"""
import sqlalchemy as sa
from alembic import op

revision = "b3e9d1f47a52"
down_revision = "a4f6c8e91b20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # همه nullable: پرونده‌های موجود تمدیدی ندارند و نباید داشته باشند. مقدارِ
    # پیش‌فرض هم عمداً نیست — «تمدید نشده» باید از «تمدید شده تا امروز» جدا بماند.
    op.add_column(
        "evaluation_records",
        sa.Column("submission_extended_until", sa.Date(), nullable=True),
    )
    op.add_column(
        "evaluation_records",
        sa.Column("submission_extended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "evaluation_records",
        sa.Column("submission_extended_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "evaluation_records",
        sa.Column("submission_extension_reason", sa.String(length=1000), nullable=True),
    )
    op.create_foreign_key(
        "fk_evaluation_records_submission_extended_by",
        "evaluation_records",
        "users",
        ["submission_extended_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_evaluation_records_submission_extended_by", "evaluation_records", type_="foreignkey"
    )
    op.drop_column("evaluation_records", "submission_extension_reason")
    op.drop_column("evaluation_records", "submission_extended_by_user_id")
    op.drop_column("evaluation_records", "submission_extended_at")
    op.drop_column("evaluation_records", "submission_extended_until")
