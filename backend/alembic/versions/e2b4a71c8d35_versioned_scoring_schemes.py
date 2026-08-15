"""طرح نمره‌دهی نسخه‌دار (P1-04)

Revision ID: e2b4a71c8d35
Revises: d7e3c81f6a94
Create Date: 2026-08-15

سه کار، و ترتیبشان مهم است:

۱. جدول `scoring_schemes` ساخته می‌شود.
۲. **نسخهٔ ۱ دقیقاً از ثابت‌های امروز ساخته و فعال می‌شود.** مقادیر این‌جا
   کپی‌برداری شده‌اند، نه import — یک مایگریشن باید همیشه همان کاری را بکند که
   روزِ نوشته‌شدنش می‌کرد. اگر از `app.core.constants` می‌خواند، عوض‌شدن آن فایل
   در آینده معنای این مایگریشن را عوض می‌کرد و بازسازی دیتابیس از صفر نتیجهٔ
   متفاوتی می‌داد.
۳. **هر پروندهٔ موجود به نسخهٔ ۱ مهر می‌خورد.** بدون این گام، پرونده‌های گذشته
   بی‌مهر می‌ماندند و اولین باری که HR طرح تازه‌ای فعال می‌کرد، محاسبهٔ مجددشان
   با قواعد جدید انجام می‌شد — یعنی دقیقاً همان بازنویسی تاریخی که این قابلیت
   برای جلوگیری از آن ساخته شده.

دستی نوشته شده. autogenerate حالا (پس از 76347be) تمیز است، ولی دادهٔ اولیه و
backfill را نمی‌سازد.
"""
import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e2b4a71c8d35"
down_revision = "d7e3c81f6a94"
branch_labels = None
depends_on = None

# ثابت‌های نمره‌دهی همان‌طور که در تاریخ این مایگریشن بودند. عمداً کپی، نه import.
V1_GENERAL_WEIGHT = 0.6
V1_SPECIALIZED_WEIGHT = 0.4
V1_EVIDENCE_REQUIRED_SCORES = [1, 5]
V1_EVIDENCE_MIN_WORDS = 3
V1_EVIDENCE_MAX_WORDS = 40
V1_THRESHOLDS = [
    {"upper_exclusive": 60, "label": "عدم تمدید / بازنگری اساسی شرایط همکاری"},
    {"upper_exclusive": 75, "label": "تمدید مشروط به برنامه بهبود مکتوب"},
    {"upper_exclusive": 90, "label": "تمدید با شرایط استاندارد"},
    {"upper_exclusive": 101, "label": "تمدید با امتیاز ویژه/ارتقاء"},
]


def upgrade() -> None:
    scheme_status = postgresql.ENUM(
        "draft", "active", "retired", name="scheme_status", create_type=False
    )
    scheme_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "scoring_schemes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, unique=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", scheme_status, nullable=False, server_default="draft"),
        sa.Column("general_section_weight", sa.Numeric(4, 3), nullable=False),
        sa.Column("specialized_section_weight", sa.Numeric(4, 3), nullable=False),
        sa.Column("evidence_required_scores", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_min_words", sa.Integer(), nullable=False),
        sa.Column("evidence_max_words", sa.Integer(), nullable=False),
        sa.Column("thresholds", postgresql.JSONB(), nullable=False),
        sa.Column("indicator_weights", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("activated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )

    # حداکثر یک طرح فعال، تضمین‌شده توسط دیتابیس — نه بررسی در کد، که در برابر
    # دو درخواست هم‌زمان بی‌فایده است.
    op.create_index(
        "uq_single_active_scheme",
        "scoring_schemes",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.add_column(
        "evaluation_records",
        sa.Column(
            "scoring_scheme_id",
            sa.Integer(),
            sa.ForeignKey("scoring_schemes.id"),
            nullable=True,
        ),
    )

    # --- نسخهٔ ۱: همان قواعدی که تا امروز در کد بود ------------------------
    op.execute(
        sa.text("""
            INSERT INTO scoring_schemes (
                version, name, status,
                general_section_weight, specialized_section_weight,
                evidence_required_scores, evidence_min_words, evidence_max_words,
                thresholds, indicator_weights, activated_at
            ) VALUES (
                1, :name, 'active',
                :gw, :sw,
                CAST(:req AS jsonb), :minw, :maxw,
                CAST(:thr AS jsonb), '{}'::jsonb, now()
            )
        """).bindparams(
            name="نسخهٔ پایه (قواعد اولیهٔ سامانه)",
            gw=V1_GENERAL_WEIGHT,
            sw=V1_SPECIALIZED_WEIGHT,
            req=json.dumps(V1_EVIDENCE_REQUIRED_SCORES),
            minw=V1_EVIDENCE_MIN_WORDS,
            maxw=V1_EVIDENCE_MAX_WORDS,
            thr=json.dumps(V1_THRESHOLDS, ensure_ascii=False),
        )
    )

    # --- مهر زدن همهٔ پرونده‌های موجود -------------------------------------
    op.execute(
        sa.text("""
            UPDATE evaluation_records
            SET scoring_scheme_id = (SELECT id FROM scoring_schemes WHERE version = 1)
            WHERE scoring_scheme_id IS NULL
        """)
    )


def downgrade() -> None:
    op.drop_column("evaluation_records", "scoring_scheme_id")
    op.drop_index("uq_single_active_scheme", table_name="scoring_schemes")
    op.drop_table("scoring_schemes")
    postgresql.ENUM(name="scheme_status").drop(op.get_bind(), checkfirst=True)
