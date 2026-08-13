"""add cancelled evaluation status

نیمهٔ اول P0-02. عمداً از مایگریشن بعدی (که ایندکس یکتای جزئی را بازمی‌سازد) جدا
است: Postgres اجازه نمی‌دهد مقدار تازهٔ یک enum در همان تراکنشی که اضافه شده استفاده
شود، و predicate آن ایندکس دقیقاً به 'cancelled' ارجاع می‌دهد. دور زدنش با
cast به text هم کار نمی‌کند (predicate ایندکس باید IMMUTABLE باشد).

Revision ID: d7a2c91fb480
Revises: c3e8b1a76d94
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd7a2c91fb480'
down_revision: Union[str, None] = 'c3e8b1a76d94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE evaluation_status ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    # Postgres حذف یک مقدار از enum را پشتیبانی نمی‌کند؛ تنها راه، بازسازی کل نوع و
    # همهٔ ستون‌های وابسته است. چون مقدار اضافه‌شده بی‌ضرر است (هیچ کدی مجبور به
    # استفاده از آن نیست) عمداً no-op می‌ماند تا downgrade خودش تبدیل به یک عملیات
    # پرریسک روی دادهٔ واقعی نشود.
    pass
