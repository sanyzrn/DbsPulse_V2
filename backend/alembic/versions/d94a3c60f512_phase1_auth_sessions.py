"""phase1 auth sessions

- جدول auth_sessions برای refresh token های قابل‌ابطال با چرخش (rotation)
- ستون users.must_change_password: بعد از ریست رمز توسط HR، کاربر در ورود بعدی
  مجبور به تعیین رمز جدید می‌شود.

Revision ID: d94a3c60f512
Revises: c7f2d81a5e30
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd94a3c60f512'
down_revision: Union[str, None] = 'c7f2d81a5e30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'auth_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('jti', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('rotated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('replaced_by_jti', sa.String(length=64), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('jti'),
    )
    op.create_index('ix_auth_sessions_user', 'auth_sessions', ['user_id'])

    op.add_column(
        'users',
        sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('users', 'must_change_password')
    op.drop_index('ix_auth_sessions_user', table_name='auth_sessions')
    op.drop_table('auth_sessions')
