"""phase4 notification dedup key

ستون dedup_key + ایندکس ترکیبی برای اعلان‌های زمان‌بندی‌شده (انقضای قرارداد، تأخیر
مراحل) تا در هر اجرای sweep دوباره ساخته نشوند.

Revision ID: d3a91c47f60b
Revises: c1f8a6b03d29
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd3a91c47f60b'
down_revision: Union[str, None] = 'c1f8a6b03d29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('notifications', sa.Column('dedup_key', sa.String(length=120), nullable=True))
    op.create_index(
        'ix_notifications_dedup', 'notifications', ['user_id', 'dedup_key', 'created_at']
    )


def downgrade() -> None:
    op.drop_index('ix_notifications_dedup', table_name='notifications')
    op.drop_column('notifications', 'dedup_key')
