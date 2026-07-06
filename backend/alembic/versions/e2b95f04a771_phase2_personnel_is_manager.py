"""phase2 personnel is_manager

مسیر ویژه «مدیر» تا الان با مقایسه متن آزاد عنوان شغلی با رشته «مدیر» فعال می‌شد؛
یک فاصله اضافی یا «ي» عربی کافی بود تا فرد بی‌صدا به مسیر عادی برود. از این پس یک
پرچم صریح is_manager منبع حقیقت است؛ ردیف‌های موجود از روی همان قانون قدیمی
مهاجرت داده می‌شوند (این تنها جایی است که رشته «مدیر» باقی می‌ماند).

Revision ID: e2b95f04a771
Revises: d94a3c60f512
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e2b95f04a771'
down_revision: Union[str, None] = 'd94a3c60f512'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'personnel',
        sa.Column('is_manager', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE personnel SET is_manager = TRUE WHERE job_title = 'مدیر'")


def downgrade() -> None:
    op.drop_column('personnel', 'is_manager')
