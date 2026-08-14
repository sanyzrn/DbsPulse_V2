"""سقف طول برای ستون‌های متنیِ آزاد (P2-05)

Revision ID: c4a1f0e93b57
Revises: 9e7b10873ee7
Create Date: 2026-08-14

سقف در schema جلوی ورودی بزرگ از API را می‌گیرد، ولی هر مسیر نوشتنِ دیگری —
seeder دمو، ورودی اکسل، مایگریشن، SQL دستی — از کنارش رد می‌شود. این مایگریشن
همان سقف‌ها را روی خودِ ستون می‌گذارد. اعداد از app/core/text_limits.py می‌آیند و
تستِ test_text_limits.py می‌سنجد که این دو از هم جدا نیفتند.

`recommendation` عمداً Text می‌ماند: مقدارش را سامانه می‌سازد
(services/evaluation.recommendation_for)، نه کاربر.

**این فایل دستی نوشته شده است.** `alembic revision --autogenerate` در این مخزن
هنوز امن نیست: ایندکس‌ها و قیدهای یکتای حیاتی (از جمله
uq_open_evaluation_per_personnel و uq_single_open_period) در مایگریشن‌ها با
op.create_index ساخته شده‌اند و روی مدل‌ها اعلام نشده‌اند، پس autogenerate آن‌ها
را «اضافی» می‌بیند و DROP پیشنهاد می‌دهد.

USING با cast صریح لازم است: Postgres تبدیل text → varchar(n) را وقتی داده‌ای
طولانی‌تر از n وجود داشته باشد رد می‌کند. left() داده را کوتاه می‌کند به‌جای
اینکه مایگریشن را بشکند — در این مرحله از پروژه هیچ داده‌ای به این طول‌ها
نزدیک نیست، ولی مایگریشنی که روی دادهٔ واقعی می‌ترکد بدترین نوع مایگریشن است.
"""
import sqlalchemy as sa
from alembic import op

revision = "c4a1f0e93b57"
down_revision = "9e7b10873ee7"
branch_labels = None
depends_on = None

# (جدول، ستون، سقف، nullable)
_COLUMNS = [
    ("evaluation_records", "evaluator_comment", 4000, True),
    ("evaluation_records", "self_assessment_note", 2000, True),
    ("evaluation_records", "objection_reason", 2000, True),
    ("evaluation_records", "objection_resolution", 2000, True),
    ("evaluation_scores", "evidence_text", 2000, True),
    ("evaluation_comments", "comment_text", 4000, False),
    ("improvement_plans", "summary", 4000, True),
    ("improvement_plan_goals", "description", 1000, False),
    ("indicators", "category", 200, False),
    ("indicators", "description", 1000, False),
    ("self_assessment_scores", "note", 1000, True),
]


def upgrade() -> None:
    for table, column, limit, nullable in _COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.Text(),
            type_=sa.String(limit),
            existing_nullable=nullable,
            postgresql_using=f"left({column}, {limit})",
        )


def downgrade() -> None:
    for table, column, limit, nullable in _COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.String(limit),
            type_=sa.Text(),
            existing_nullable=nullable,
        )
