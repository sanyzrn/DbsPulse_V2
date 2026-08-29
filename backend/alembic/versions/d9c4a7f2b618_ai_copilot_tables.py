"""دستیار هوشمند → همکارِ همه‌کاره: کنش‌های در انتظار تأیید، بارگذاری فایل، تنظیمات حلقه.

Revision ID: d9c4a7f2b618
Revises: f2a7d3c9e861
Create Date: 2026-08-30

سه چیز اضافه می‌شود:

* `ai_pending_actions` — کنشِ تغییردهنده‌ای که مدل پیشنهاد داده و آدم باید
  تأییدش کند. جدول است و نه JSON داخل پیام، چون باید سرور بتواند وضعیتِ هر
  پیشنهاد را جدا از تاریخچهٔ گفت‌وگو پاسخ دهد: «این قبلاً اجرا شده»، «این
  منقضی شده».
* `ai_uploads` — فایل‌های بارگذاری‌شده در گفت‌وگو، با بایت‌های خام؛
  اعتبارسنجیِ دوباره باید از روی خودِ فایل انجام شود، نه از روی JSON.
* سه ستونِ تنظیمات: عمقِ حلقهٔ ابزار، و اجازه/سقفِ بارگذاری فایل.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9c4a7f2b618"
down_revision: str | None = "f2a7d3c9e861"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_messages",
        sa.Column("meta_json", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "ai_settings",
        sa.Column("max_tool_iterations", sa.Integer(), nullable=False, server_default="6"),
    )
    op.add_column(
        "ai_settings",
        sa.Column("allow_uploads", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "ai_settings",
        sa.Column("max_upload_mb", sa.Integer(), nullable=False, server_default="5"),
    )

    op.create_table(
        "ai_pending_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("arguments_json", sa.Text(), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("result_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now() + interval '24 hours'"),
        ),
    )
    op.create_index("ix_ai_pending_actions_conversation_id", "ai_pending_actions", ["conversation_id"])
    op.create_index("ix_ai_pending_actions_user_id", "ai_pending_actions", ["user_id"])
    op.create_index("ix_ai_pending_actions_status", "ai_pending_actions", ["status"])

    op.create_table(
        "ai_uploads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("mime_type", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("structure_json", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_uploads_conversation_id", "ai_uploads", ["conversation_id"])
    op.create_index("ix_ai_uploads_user_id", "ai_uploads", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_uploads_user_id", table_name="ai_uploads")
    op.drop_index("ix_ai_uploads_conversation_id", table_name="ai_uploads")
    op.drop_table("ai_uploads")
    op.drop_index("ix_ai_pending_actions_status", table_name="ai_pending_actions")
    op.drop_index("ix_ai_pending_actions_user_id", table_name="ai_pending_actions")
    op.drop_index("ix_ai_pending_actions_conversation_id", table_name="ai_pending_actions")
    op.drop_table("ai_pending_actions")
    op.drop_column("ai_settings", "max_upload_mb")
    op.drop_column("ai_settings", "allow_uploads")
    op.drop_column("ai_settings", "max_tool_iterations")
    op.drop_column("ai_messages", "meta_json")
