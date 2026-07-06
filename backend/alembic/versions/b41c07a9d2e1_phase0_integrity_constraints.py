"""phase0 integrity constraints

- یکتایی evaluation_access.personnel_id (پیش از آن ردیف‌های تکراری احتمالی پاک‌سازی
  می‌شوند و جدیدترین ردیف بر اساس updated_at نگه داشته می‌شود)
- حداکثر یک ارزیابی باز (نهایی‌نشده) به ازای هر پرسنل (ایندکس یکتای جزئی)
  توجه: اگر دیتابیس موجود چند ارزیابی باز برای یک پرسنل داشته باشد این migration
  عمداً fail می‌شود؛ باید ابتدا به‌صورت دستی تعیین تکلیف شوند (حذف/نهایی‌سازی).
- backfill مقدار recommendation برای رکوردهایی که به‌خاطر شکاف بازه‌های قبلی
  (مثلاً امتیاز ۵۹٫۵) بدون نتیجه مانده بودند.

Revision ID: b41c07a9d2e1
Revises: 863122fc8f4a
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b41c07a9d2e1'
down_revision: Union[str, None] = '863122fc8f4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM evaluation_access a
        USING evaluation_access b
        WHERE a.personnel_id = b.personnel_id
          AND (a.updated_at < b.updated_at
               OR (a.updated_at = b.updated_at AND a.id < b.id))
        """
    )
    op.create_unique_constraint(
        "uq_evaluation_access_personnel_id", "evaluation_access", ["personnel_id"]
    )

    op.create_index(
        "uq_open_evaluation_per_personnel",
        "evaluation_records",
        ["subject_personnel_id"],
        unique=True,
        postgresql_where=sa.text("status != 'finalized'"),
    )

    op.execute(
        """
        UPDATE evaluation_records
        SET recommendation = CASE
            WHEN final_weighted_pct < 60 THEN 'عدم تمدید / بازنگری اساسی شرایط همکاری'
            WHEN final_weighted_pct < 75 THEN 'تمدید مشروط به برنامه بهبود مکتوب'
            WHEN final_weighted_pct < 90 THEN 'تمدید با شرایط استاندارد'
            ELSE 'تمدید با امتیاز ویژه/ارتقاء'
        END
        WHERE recommendation IS NULL AND final_weighted_pct IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("uq_open_evaluation_per_personnel", table_name="evaluation_records")
    op.drop_constraint(
        "uq_evaluation_access_personnel_id", "evaluation_access", type_="unique"
    )
