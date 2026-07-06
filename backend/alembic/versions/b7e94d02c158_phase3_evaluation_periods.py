"""phase3 evaluation periods

دوره‌های (کمپین) ارزیابی: جدول evaluation_periods + ستون period_id روی
evaluation_records. ایندکس یکتای جزئی تضمین می‌کند در هر لحظه حداکثر یک دوره
باز وجود داشته باشد.

Revision ID: b7e94d02c158
Revises: a8d5e13c47b6
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7e94d02c158'
down_revision: Union[str, None] = 'a8d5e13c47b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # create_type=False تا create_table دوباره تلاش به ساخت type نکند
    period_status = postgresql.ENUM('open', 'closed', name='period_status', create_type=False)
    period_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'evaluation_periods',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('starts_on', sa.Date(), nullable=False),
        sa.Column('ends_on', sa.Date(), nullable=False),
        sa.Column('status', period_status, nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    # حداکثر یک دوره باز: یکتایی روی مقدار ثابت status فقط برای ردیف‌های باز
    op.create_index(
        'uq_single_open_period',
        'evaluation_periods',
        ['status'],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )

    op.add_column(
        'evaluation_records',
        sa.Column('period_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_evaluation_records_period_id',
        'evaluation_records',
        'evaluation_periods',
        ['period_id'],
        ['id'],
    )
    op.create_index('ix_evaluation_records_period', 'evaluation_records', ['period_id'])


def downgrade() -> None:
    op.drop_index('ix_evaluation_records_period', table_name='evaluation_records')
    op.drop_constraint('fk_evaluation_records_period_id', 'evaluation_records', type_='foreignkey')
    op.drop_column('evaluation_records', 'period_id')
    op.drop_index('uq_single_open_period', table_name='evaluation_periods')
    op.drop_table('evaluation_periods')
    sa.Enum(name='period_status').drop(op.get_bind(), checkfirst=True)
