"""phase2 drop stage column

ستون stage همیشه ۱:۱ از status قابل استخراج بود (draft→supervisor_scoring،
submitted→hr_review، hr_approved→deputy_review، deputy_approved/finalized→ceo_final)
و دو ستونِ هم‌معنا که دستی همگام نگه داشته می‌شدند منبع باگ بود. از این پس stage
فقط در لایه API از status مشتق می‌شود.

Revision ID: f6c1a8d27e93
Revises: e2b95f04a771
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f6c1a8d27e93'
down_revision: Union[str, None] = 'e2b95f04a771'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('evaluation_records', 'stage')
    sa.Enum(name='evaluation_stage').drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    stage_enum = sa.Enum(
        'supervisor_scoring', 'hr_review', 'deputy_review', 'ceo_final',
        name='evaluation_stage',
    )
    stage_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'evaluation_records',
        sa.Column('stage', stage_enum, nullable=True),
    )
    op.execute(
        """
        UPDATE evaluation_records SET stage = CASE status
            WHEN 'draft' THEN 'supervisor_scoring'::evaluation_stage
            WHEN 'submitted' THEN 'hr_review'::evaluation_stage
            WHEN 'hr_approved' THEN 'deputy_review'::evaluation_stage
            ELSE 'ceo_final'::evaluation_stage
        END
        """
    )
    op.alter_column('evaluation_records', 'stage', nullable=False)
