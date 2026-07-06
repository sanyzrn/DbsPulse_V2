"""phase4 improvement plans

برنامه‌های بهبود (R13.2): جدول improvement_plans (هر ارزیابی حداکثر یک برنامه)
و improvement_plan_goals (چک‌لیست اهداف). با نتیجه «تمدید مشروط به برنامه بهبود
مکتوب» گره خورده است.

Revision ID: f1c93b7ad025
Revises: e8a4b1c9d7f2
Create Date: 2026-07-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f1c93b7ad025'
down_revision: Union[str, None] = 'e8a4b1c9d7f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    plan_status = postgresql.ENUM(
        'open', 'completed', 'cancelled', name='improvement_plan_status', create_type=False
    )
    plan_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'improvement_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('evaluation_record_id', sa.Integer(), nullable=False),
        sa.Column('personnel_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('owner_user_id', sa.Integer(), nullable=True),
        sa.Column('status', plan_status, nullable=False),
        sa.Column('review_date', sa.Date(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('follow_up_evaluation_id', sa.Integer(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['evaluation_record_id'], ['evaluation_records.id']),
        sa.ForeignKeyConstraint(['personnel_id'], ['personnel.id']),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['follow_up_evaluation_id'], ['evaluation_records.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('evaluation_record_id', name='uq_improvement_plan_evaluation'),
    )
    op.create_index('ix_improvement_plans_status', 'improvement_plans', ['status'])
    op.create_index('ix_improvement_plans_personnel', 'improvement_plans', ['personnel_id'])

    op.create_table(
        'improvement_plan_goals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('is_done', sa.Boolean(), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['improvement_plans.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_improvement_plan_goals_plan', 'improvement_plan_goals', ['plan_id'])


def downgrade() -> None:
    op.drop_index('ix_improvement_plan_goals_plan', table_name='improvement_plan_goals')
    op.drop_table('improvement_plan_goals')
    op.drop_index('ix_improvement_plans_personnel', table_name='improvement_plans')
    op.drop_index('ix_improvement_plans_status', table_name='improvement_plans')
    op.drop_table('improvement_plans')
    sa.Enum(name='improvement_plan_status').drop(op.get_bind(), checkfirst=True)
