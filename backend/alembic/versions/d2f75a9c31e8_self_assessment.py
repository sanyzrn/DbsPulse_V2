"""self assessment

P0-06 — دیدگاه خودِ کارمند، ثبت‌شده پیش از قطعی‌شدن نمرهٔ ارزیاب.

جدول عمداً از evaluation_scores جداست، نه یک ستون کنار آن: محاسبهٔ نتیجه فقط از
evaluation_scores می‌خواند، پس این جدایی *به‌طور ساختاری* تضمین می‌کند نظر کارمند
هرگز وارد میانگین نمی‌شود — نه به این دلیل که یک شرط جایی یادش نرفته باشد.

Revision ID: d2f75a9c31e8
Revises: a6d1e83b5c47
Create Date: 2026-08-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd2f75a9c31e8'
down_revision: Union[str, None] = 'a6d1e83b5c47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evaluation_records",
        sa.Column("self_assessment_submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("evaluation_records", sa.Column("self_assessment_note", sa.Text(), nullable=True))

    op.create_table(
        "self_assessment_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "evaluation_record_id",
            sa.Integer(),
            sa.ForeignKey("evaluation_records.id"),
            nullable=False,
        ),
        sa.Column("indicator_id", sa.Integer(), sa.ForeignKey("indicators.id"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("score BETWEEN 1 AND 5", name="ck_self_assessment_scores_score_range"),
        sa.UniqueConstraint(
            "evaluation_record_id", "indicator_id", name="uq_self_assessment_record_indicator"
        ),
    )
    op.create_index(
        "ix_self_assessment_scores_record",
        "self_assessment_scores",
        ["evaluation_record_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_self_assessment_scores_record", table_name="self_assessment_scores")
    op.drop_table("self_assessment_scores")
    op.drop_column("evaluation_records", "self_assessment_note")
    op.drop_column("evaluation_records", "self_assessment_submitted_at")
