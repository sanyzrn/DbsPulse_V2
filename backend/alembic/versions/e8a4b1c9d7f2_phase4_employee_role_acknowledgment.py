"""phase4 employee role + acknowledgment

نقش جدید «employee» به enum نقش‌ها اضافه می‌شود (کارمند فقط نتیجه نهایی ارزیابی
خودش را می‌بیند) و ستون‌های رؤیت رسمی (acknowledged_at / acknowledged_by_user_id)
به پرونده ارزیابی اضافه می‌شوند.

Revision ID: e8a4b1c9d7f2
Revises: d3a91c47f60b
Create Date: 2026-07-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e8a4b1c9d7f2'
down_revision: Union[str, None] = 'd3a91c47f60b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # از PostgreSQL 12 به بعد افزودن مقدار enum داخل تراکنش مجاز است،
    # به شرطی که در همان تراکنش استفاده نشود (اینجا نمی‌شود).
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'employee'")
    op.add_column(
        'evaluation_records',
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'evaluation_records',
        sa.Column('acknowledged_by_user_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_evaluation_records_acknowledged_by_user_id',
        'evaluation_records',
        'users',
        ['acknowledged_by_user_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_evaluation_records_acknowledged_by_user_id',
        'evaluation_records',
        type_='foreignkey',
    )
    op.drop_column('evaluation_records', 'acknowledged_by_user_id')
    op.drop_column('evaluation_records', 'acknowledged_at')
    # حذف مقدار از enum در PostgreSQL پشتیبانی نمی‌شود؛ مقدار 'employee' باقی می‌ماند
