"""scheduler runs and stage clock

P0-08 — تاریخچهٔ اجرای زمان‌بند، تا «اجرا شد و چیزی نبود» از «اصلاً اجرا نشد» قابل
تشخیص باشد.

P1-02 — ساعتِ مرحله. جاروی SLA از created_at استفاده می‌کرد، یعنی «سن کل پرونده»
نه «چقدر در این مرحله مانده». backfill با created_at انجام می‌شود چون بهترین تخمین
موجود از ورود به مرحلهٔ فعلی است؛ از آن به بعد هر گذار خودش مقدار را به‌روز می‌کند.

Revision ID: c95f2e6a4d18
Revises: b8e34f712a05
Create Date: 2026-08-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c95f2e6a4d18'
down_revision: Union[str, None] = 'b8e34f712a05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evaluation_records",
        sa.Column(
            "stage_entered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.execute("UPDATE evaluation_records SET stage_entered_at = created_at")
    # جاروی SLA روی همین ستون فیلتر می‌کند
    op.create_index(
        "ix_evaluation_records_stage_entered_at", "evaluation_records", ["stage_entered_at"]
    )

    op.create_table(
        "scheduler_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_scheduler_runs_started_at", "scheduler_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_scheduler_runs_started_at", table_name="scheduler_runs")
    op.drop_table("scheduler_runs")
    op.drop_index("ix_evaluation_records_stage_entered_at", table_name="evaluation_records")
    op.drop_column("evaluation_records", "stage_entered_at")
