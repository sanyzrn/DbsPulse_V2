"""employee objection

P0-06 — مسیر اعتراض کارمند به نتیجهٔ نهایی.

«رؤیت» فقط ثبت می‌کرد که فرد نتیجه را *دید*، نه این‌که پذیرفت. بدون این ستون‌ها،
سامانه هیچ جایی برای مخالفت او نداشت و در هر بازبینی حقوقی پاسخِ «کارمند چه گفت؟»
می‌شد «هیچ‌چیز ثبت نشده».

نتیجه و سند نهایی عمداً دست‌نخورده می‌مانند: اعتراض یک رکورد موازی است، نه بازنویسی
سندی که هش و QR تأیید دارد.

Revision ID: a6d1e83b5c47
Revises: c95f2e6a4d18
Create Date: 2026-08-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a6d1e83b5c47'
down_revision: Union[str, None] = 'c95f2e6a4d18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("evaluation_records", sa.Column("objection_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("evaluation_records", sa.Column("objection_reason", sa.Text(), nullable=True))
    op.add_column(
        "evaluation_records", sa.Column("objection_resolved_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("evaluation_records", sa.Column("objection_resolution", sa.Text(), nullable=True))
    op.add_column(
        "evaluation_records", sa.Column("objection_resolved_by_user_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_evaluation_records_objection_resolved_by",
        "evaluation_records",
        "users",
        ["objection_resolved_by_user_id"],
        ["id"],
    )
    # صف «اعتراض‌های بی‌پاسخ» برای HR روی همین شرط فیلتر می‌کند
    op.create_index(
        "ix_evaluation_records_open_objection",
        "evaluation_records",
        ["objection_at"],
        postgresql_where=sa.text("objection_at IS NOT NULL AND objection_resolved_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_records_open_objection", table_name="evaluation_records")
    op.drop_constraint(
        "fk_evaluation_records_objection_resolved_by", "evaluation_records", type_="foreignkey"
    )
    op.drop_column("evaluation_records", "objection_resolved_by_user_id")
    op.drop_column("evaluation_records", "objection_resolution")
    op.drop_column("evaluation_records", "objection_resolved_at")
    op.drop_column("evaluation_records", "objection_reason")
    op.drop_column("evaluation_records", "objection_at")
