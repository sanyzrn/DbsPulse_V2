"""add token_version to users

Revision ID: 863122fc8f4a
Revises: 1eaa459f4dde
Create Date: 2026-07-02 08:15:17.729276

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '863122fc8f4a'
down_revision: Union[str, None] = '1eaa459f4dde'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default فقط برای backfill رکوردهای موجود لازم است؛ مقدار پیش‌فرض در ORM جدا مدیریت می‌شود
    op.add_column(
        'users', sa.Column('token_version', sa.Integer(), nullable=False, server_default='0')
    )
    op.alter_column('users', 'token_version', server_default=None)
    # نکته: create_foreign_key برای fk_users_personnel_id عمداً حذف شده — این محدودیت
    # از قبل در migration اولیه (0e25894e177a) با use_alter=True ساخته شده؛ alembic
    # autogenerate آن را به اشتباه به‌عنوان تغییر جدید تشخیص می‌دهد (یک quirk شناخته‌شده
    # با ForeignKey هایی که use_alter=True دارند).


def downgrade() -> None:
    op.drop_column('users', 'token_version')
