"""hr filter/sort indexes

ایندکس روی ستون‌هایی که در فیلترها/مرتب‌سازی‌های پرکاربرد HR استفاده می‌شوند و تا
این‌جا ایندکس نداشتند: واحد سازمانی و وضعیت پرسنل (فیلترهای فهرست پرسنل و ستون
مرتب‌سازی)، امتیاز نهایی وزنی (فیلتر بازهٔ امتیاز و گزارش‌ها)، تاریخ بازنگری برنامهٔ
بهبود (ترتیب پیش‌فرض فهرست) و وضعیت کاربر. بدون این‌ها فیلترها روی جدول‌های بزرگ
sequential scan می‌شدند.

Revision ID: d5b1f3e7c920
Revises: c4f7e2a9b103
Create Date: 2026-07-11

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd5b1f3e7c920'
down_revision: Union[str, None] = 'c4f7e2a9b103'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = [
    ("ix_personnel_org_unit", "personnel", ["org_unit"]),
    ("ix_personnel_status", "personnel", ["status"]),
    ("ix_evaluation_records_final_pct", "evaluation_records", ["final_weighted_pct"]),
    ("ix_improvement_plans_review_date", "improvement_plans", ["review_date"]),
    ("ix_users_is_active", "users", ["is_active"]),
]


def upgrade() -> None:
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _ in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
