"""threaded comment replies

پاسخ‌های threaded روی کامنت‌های پرونده (مثلاً پاسخ ارزیاب به دلیلِ برگشت). یک ستون
خودارجاع parent_comment_id به evaluation_comments اضافه می‌شود؛ null یعنی کامنت
سطح‌بالا و مقدار غیرnull یعنی پاسخ (فقط یک سطح عمق، در سطح اپلیکیشن کنترل می‌شود).
حذف کامنتِ والد، پاسخ‌هایش را هم CASCADE حذف می‌کند.

Revision ID: c4f7e2a9b103
Revises: b28cc6abdf2a
Create Date: 2026-07-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4f7e2a9b103'
down_revision: Union[str, None] = 'b28cc6abdf2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'evaluation_comments',
        sa.Column('parent_comment_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_evaluation_comments_parent',
        'evaluation_comments',
        'evaluation_comments',
        ['parent_comment_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.create_index(
        'ix_evaluation_comments_parent_comment_id',
        'evaluation_comments',
        ['parent_comment_id'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_evaluation_comments_parent_comment_id', table_name='evaluation_comments'
    )
    op.drop_constraint(
        'fk_evaluation_comments_parent', 'evaluation_comments', type_='foreignkey'
    )
    op.drop_column('evaluation_comments', 'parent_comment_id')
