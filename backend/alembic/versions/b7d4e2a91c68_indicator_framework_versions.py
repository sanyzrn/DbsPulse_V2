"""نسخه‌دار کردن چارچوب شاخص‌ها (P1-05)

Revision ID: b7d4e2a91c68
Revises: a83f61b0d472
Create Date: 2026-08-16

سه گام، به همان ترتیبی که `e2b4a71c8d35` برای طرح نمره‌دهی رفت:

۱. جدول `indicator_frameworks` ساخته می‌شود.
۲. **نسخهٔ ۱ از مجموعهٔ شاخص‌های فعالِ همین لحظه ساخته می‌شود.** برخلاف طرح
   نمره‌دهی، این‌جا هیچ ثابتی برای کپی‌کردن وجود ندارد — عضویت یک واقعیتِ درون
   دیتابیس است، پس از خودِ دیتابیس خوانده می‌شود. همین باعث می‌شود مایگریشن روی
   هر استقراری (با هر مجموعه شاخصی) درست کار کند.
۳. **هر پروندهٔ موجود به نسخهٔ ۱ مهر می‌خورد.** بدون این گام، پرونده‌های باز
   بی‌مهر می‌ماندند و همچنان با «شاخص‌های فعالِ امروز» سنجیده می‌شدند — یعنی
   همان خرابی‌ای که این مایگریشن برای بستنش نوشته شده، برای پرونده‌های موجود
   باز می‌ماند. دقیقاً همان‌هایی که بیشتر از همه در معرضش‌اند.

دستی نوشته شده: autogenerate جدول و ستون را می‌سازد ولی دادهٔ اولیه و backfill را نه.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b7d4e2a91c68"
down_revision = "a83f61b0d472"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "indicator_frameworks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, unique=True),
        sa.Column("member_ids", postgresql.JSONB(), nullable=False),
        sa.Column("change_kind", sa.String(length=30), nullable=False),
        sa.Column("change_note", sa.String(length=500), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.add_column(
        "evaluation_records",
        sa.Column(
            "indicator_framework_id",
            sa.Integer(),
            sa.ForeignKey("indicator_frameworks.id"),
            nullable=True,
        ),
    )

    # --- نسخهٔ ۱: مجموعهٔ فعالِ همین لحظه ------------------------------------
    # COALESCE لازم است: روی دیتابیسی که هنوز شاخصی ندارد (نصب تازه، قبل از
    # seed) آرایهٔ خالی می‌دهد به‌جای NULL که ستون NOT NULL را می‌شکست.
    op.execute(
        sa.text("""
            INSERT INTO indicator_frameworks (version, member_ids, change_kind)
            SELECT
                1,
                COALESCE(
                    (SELECT jsonb_agg(id ORDER BY id) FROM indicators WHERE is_active = true),
                    '[]'::jsonb
                ),
                'seed'
        """)
    )

    # --- مهر زدن همهٔ پرونده‌های موجود -------------------------------------
    op.execute(
        sa.text("""
            UPDATE evaluation_records
            SET indicator_framework_id = (SELECT id FROM indicator_frameworks WHERE version = 1)
            WHERE indicator_framework_id IS NULL
        """)
    )


def downgrade() -> None:
    op.drop_column("evaluation_records", "indicator_framework_id")
    op.drop_table("indicator_frameworks")
