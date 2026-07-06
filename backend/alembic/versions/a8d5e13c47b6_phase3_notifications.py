"""phase3 notifications

جدول اعلان‌های درون‌برنامه‌ای (زنگوله): هر گذار گردش‌کار برای نفر بعدیِ زنجیره
اعلان می‌سازد تا سیستم از حالت کاملاً pull-based خارج شود.

Revision ID: a8d5e13c47b6
Revises: f6c1a8d27e93
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a8d5e13c47b6'
down_revision: Union[str, None] = 'f6c1a8d27e93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('link', sa.String(length=255), nullable=True),
        sa.Column('evaluation_record_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['evaluation_record_id'], ['evaluation_records.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    # کوئری اصلی: اعلان‌های یک کاربر، خوانده‌نشده‌ها اول، به ترتیب زمان
    op.create_index('ix_notifications_user_read', 'notifications', ['user_id', 'read_at'])
    op.create_index('ix_notifications_created_at', 'notifications', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_notifications_created_at', table_name='notifications')
    op.drop_index('ix_notifications_user_read', table_name='notifications')
    op.drop_table('notifications')
