"""دستیار هوشمند: تنظیمات، دسترسی هر کاربر، و تاریخچهٔ گفت‌وگو

مجوز `manage_ai` عمداً از `manage_modules` جدا شد: خاموش‌کردن یک بخش از سامانه
با «کدام کاربر کلید API کدام سرویس بیرونی را دارد» یک جنس نیست. دومی هم هزینه
دارد و هم داده را از سازمان بیرون می‌فرستد، پس باید صریح داده شود.

هیچ ردیفِ دسترسی ساخته نمی‌شود. نبودِ ردیف یعنی «دستیار ندارد» — یعنی حالت
پیش‌فرضِ هر حساب، از جمله حساب‌هایی که همین حالا وجود دارند، خاموش است.

Revision ID: c1a5e70bd932
Revises: 35ea3c955ab3
Create Date: 2026-08-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "c1a5e70bd932"
down_revision: str | None = "35ea3c955ab3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("ALTER TYPE capability ADD VALUE IF NOT EXISTS 'manage_ai'"))
    # مقدارِ تازهٔ enum تا پایان همین تراکنش قابل *استفاده* نیست.
    conn.execute(text("COMMIT"))

    op.create_table(
        "ai_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("base_url", sa.String(length=300), server_default="", nullable=False),
        sa.Column("model", sa.String(length=120), server_default="", nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), server_default="", nullable=False),
        sa.Column("temperature", sa.Integer(), server_default="30", nullable=False),
        sa.Column("max_tokens", sa.Integer(), server_default="1200", nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), server_default="60", nullable=False),
        sa.Column("instructions", sa.Text(), server_default="", nullable=False),
        sa.Column("restrict_to_platform", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("context_record_limit", sa.Integer(), server_default="25", nullable=False),
        sa.Column("allow_write_actions", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("max_user_chars", sa.Integer(), server_default="4000", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ai_user_access",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), server_default="", nullable=False),
        sa.Column("model", sa.String(length=120), server_default="", nullable=False),
        sa.Column("allow_write_actions", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("daily_message_limit", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # قید یکتا و نه «قید + ایندکس»: پستگرس خودش پشتِ قید یکتا ایندکس
        # می‌سازد، و دوتاکردنشان فقط یک تفاوتِ کاذب در autogenerate می‌شود.
        sa.UniqueConstraint("user_id", name="uq_ai_user_access_user_id"),
    )

    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), server_default="", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_conversations_user_id", "ai_conversations", ["user_id"])

    op.create_table(
        "ai_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("actions_json", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_messages_conversation_id", "ai_messages", ["conversation_id"])

    # مجوز به همان حساب‌هایی می‌رسد که همین حالا «مدیر سامانه»اند.
    conn.execute(
        text(
            """
            INSERT INTO user_capabilities (user_id, capability)
            SELECT DISTINCT uc.user_id, 'manage_ai'::capability
            FROM user_capabilities uc
            WHERE uc.capability = 'manage_capabilities'
            ON CONFLICT (user_id, capability) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
    op.drop_table("ai_user_access")
    op.drop_table("ai_settings")
    # مقدارِ enum برداشته نمی‌شود: PostgreSQL راهی برای حذف یک مقدار ندارد جز
    # بازساختنِ کل نوع. ردیف‌ها پاک می‌شوند، که رفتار را برمی‌گرداند.
    op.get_bind().execute(text("DELETE FROM user_capabilities WHERE capability = 'manage_ai'"))
