"""phase4 evaluation documents

آرشیو PDF نهایی + هش SHA-256 برای تأیید اصالت (نسخه چاپی از طریق QR).

Revision ID: c1f8a6b03d29
Revises: b7e94d02c158
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c1f8a6b03d29'
down_revision: Union[str, None] = 'b7e94d02c158'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'evaluation_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('evaluation_record_id', sa.Integer(), nullable=False),
        sa.Column('pdf_bytes', sa.LargeBinary(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['evaluation_record_id'], ['evaluation_records.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('evaluation_record_id'),
    )


def downgrade() -> None:
    op.drop_table('evaluation_documents')
