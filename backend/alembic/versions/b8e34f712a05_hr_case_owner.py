"""hr case owner

P0-03 (نیمهٔ کوتاه‌مدت) — مسئولِ HR برای هر پرونده.

سه مرحلهٔ دیگر (مسئول واحد، معاونت، مدیرعامل) همیشه صاحب مشخصی داشتند و گذارشان
برابری `current_user.id` با آن صاحب را لازم دارد. مرحلهٔ HR این را نداشت:
`assignee_field=None` بود، یعنی هر کاربر HR روی هر پرونده‌ای می‌توانست تأیید یا
برگشت بزند. در سازمانی با چند نفر HR، «مسئولِ این پرونده» اصلاً وجود نداشت.

NULL یعنی هنوز claim نشده و پرونده در صف مشترک HR است — پس مایگریشن روی داده‌های
موجود امن است و نیازی به backfill ندارد.

Revision ID: b8e34f712a05
Revises: f2c60a8bd139
Create Date: 2026-08-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8e34f712a05'
down_revision: Union[str, None] = 'f2c60a8bd139'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evaluation_records", sa.Column("hr_user_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_evaluation_records_hr_user_id", "evaluation_records", "users", ["hr_user_id"], ["id"]
    )
    # «پرونده‌های من» برای یک کاربر HR روی همین ستون فیلتر می‌کند
    op.create_index(
        "ix_evaluation_records_hr_user_id", "evaluation_records", ["hr_user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_records_hr_user_id", table_name="evaluation_records")
    op.drop_constraint("fk_evaluation_records_hr_user_id", "evaluation_records", type_="foreignkey")
    op.drop_column("evaluation_records", "hr_user_id")
