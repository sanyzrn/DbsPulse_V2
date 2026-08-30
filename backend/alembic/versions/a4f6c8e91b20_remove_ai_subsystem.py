"""Remove the AI subsystem and all of its stored data.

Revision ID: a4f6c8e91b20
Revises: d9c4a7f2b618
Create Date: 2026-08-30

This migration is intentionally destructive: conversations, messages, uploads,
pending actions, provider settings, API keys, per-user access rows, and the
``manage_ai`` capability are permanently removed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "a4f6c8e91b20"
down_revision: str | None = "d9c4a7f2b618"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CAPABILITIES_WITHOUT_AI = (
    "manage_users",
    "manage_scoring",
    "manage_integrations",
    "manage_modules",
    "view_diagnostics",
    "manage_capabilities",
    "view_audit_log",
    "manage_personnel",
)


def upgrade() -> None:
    op.drop_table("ai_uploads")
    op.drop_table("ai_pending_actions")
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
    op.drop_table("ai_user_access")
    op.drop_table("ai_settings")

    # PostgreSQL cannot DROP VALUE from an enum. Rebuild it after deleting the
    # now-invalid rows so the database schema matches the Python enum exactly.
    op.execute("DELETE FROM user_capabilities WHERE capability::text = 'manage_ai'")
    op.execute("ALTER TYPE capability RENAME TO capability_with_ai")
    values = ", ".join(f"'{value}'" for value in CAPABILITIES_WITHOUT_AI)
    op.execute(f"CREATE TYPE capability AS ENUM ({values})")
    op.execute(
        "ALTER TABLE user_capabilities "
        "ALTER COLUMN capability TYPE capability "
        "USING capability::text::capability"
    )
    op.execute("DROP TYPE capability_with_ai")


def downgrade() -> None:
    # The schema can be restored, but deleted AI data and keys cannot.
    op.execute("ALTER TYPE capability ADD VALUE IF NOT EXISTS 'manage_ai'")

    op.create_table(
        "ai_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="custom"),
        sa.Column("base_url", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("model", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False, server_default=""),
        sa.Column("temperature", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="1200"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("instructions", sa.Text(), nullable=False, server_default=""),
        sa.Column("restrict_to_platform", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("context_record_limit", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("allow_write_actions", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_user_chars", sa.Integer(), nullable=False, server_default="4000"),
        sa.Column("max_tool_iterations", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("allow_uploads", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_upload_mb", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "ai_user_access",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False, server_default=""),
        sa.Column("model", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("allow_write_actions", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("daily_message_limit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_ai_user_access_user_id"),
    )
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_conversations_user_id", "ai_conversations", ["user_id"])
    op.create_table(
        "ai_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("actions_json", sa.Text(), nullable=False, server_default=""),
        sa.Column("meta_json", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_messages_conversation_id", "ai_messages", ["conversation_id"])
    op.create_table(
        "ai_pending_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("arguments_json", sa.Text(), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("result_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now() + interval '24 hours'")),
    )
    op.create_index("ix_ai_pending_actions_conversation_id", "ai_pending_actions", ["conversation_id"])
    op.create_index("ix_ai_pending_actions_user_id", "ai_pending_actions", ["user_id"])
    op.create_index("ix_ai_pending_actions_status", "ai_pending_actions", ["status"])
    op.create_table(
        "ai_uploads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
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
