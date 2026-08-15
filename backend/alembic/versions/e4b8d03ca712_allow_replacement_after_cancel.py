"""allow replacement after cancel

نیمهٔ دوم P0-02. ایندکس یکتای جزئی «حداکثر یک ارزیابی باز به ازای هر پرسنل» تا امروز
predicate اش `status != 'finalized'` بود، یعنی پروندهٔ لغوشده هم «باز» حساب می‌شد و
همچنان جلوی ساخت پروندهٔ جایگزین را می‌گرفت — که کل هدف لغو را از بین می‌برد.

Revision ID: e4b8d03ca712
Revises: d7a2c91fb480
Create Date: 2026-08-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e4b8d03ca712'
down_revision: Union[str, None] = 'd7a2c91fb480'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "uq_open_evaluation_per_personnel"


def upgrade() -> None:
    op.drop_index(_INDEX, table_name="evaluation_records")
    op.create_index(
        _INDEX,
        "evaluation_records",
        ["subject_personnel_id"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('finalized', 'cancelled')"),
    )


def downgrade() -> None:
    # برگرداندن predicate قدیمی فقط وقتی ممکن است که هیچ پرسنلی هم‌زمان یک پروندهٔ
    # لغوشده و یک پروندهٔ باز نداشته باشد — دقیقاً حالتی که این مایگریشن ممکنش کرد.
    # اگر چنین داده‌ای وجود داشته باشد ساخت ایندکس عمداً fail می‌شود تا داده بی‌صدا
    # از بین نرود.
    op.drop_index(_INDEX, table_name="evaluation_records")
    op.create_index(
        _INDEX,
        "evaluation_records",
        ["subject_personnel_id"],
        unique=True,
        postgresql_where=sa.text("status != 'finalized'"),
    )
