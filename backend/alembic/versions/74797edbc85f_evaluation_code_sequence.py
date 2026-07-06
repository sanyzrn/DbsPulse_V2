"""evaluation code sequence

Revision ID: 74797edbc85f
Revises: 65a700d744d4
Create Date: 2026-07-01 03:43:16.756496

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '74797edbc85f'
down_revision: Union[str, None] = '65a700d744d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE evaluation_code_seq START WITH 1 INCREMENT BY 1")


def downgrade() -> None:
    op.execute("DROP SEQUENCE evaluation_code_seq")
