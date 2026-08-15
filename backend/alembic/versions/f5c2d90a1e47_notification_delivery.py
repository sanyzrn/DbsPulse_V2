"""صندوق خروجی اعلان‌ها و ارجحیت تماس کاربران (P1-03)

Revision ID: f5c2d90a1e47
Revises: e2b4a71c8d35
Create Date: 2026-08-15

هیچ رفتاری با این مایگریشن عوض نمی‌شود: تا وقتی هیچ کانالی در `.env` تنظیم نشده
باشد، هیچ ردیفی در صندوق خروجی ساخته نمی‌شود و اعلان‌ها فقط درون‌برنامه‌ای می‌مانند.

ارجحیت‌ها پیش‌فرض **خاموش** ثبت می‌شوند و این عمدی است. اگر پیش‌فرض روشن بود،
اولین باری که کسی یک کانال را تنظیم می‌کرد، کل سازمان بی‌خبر پیام می‌گرفت.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f5c2d90a1e47"
down_revision = "e2b4a71c8d35"
branch_labels = None
depends_on = None


def upgrade() -> None:
    delivery_channel = postgresql.ENUM("email", "sms", name="delivery_channel", create_type=False)
    delivery_status = postgresql.ENUM(
        "pending", "sent", "failed", "abandoned", name="delivery_status", create_type=False
    )
    delivery_channel.create(op.get_bind(), checkfirst=True)
    delivery_status.create(op.get_bind(), checkfirst=True)

    op.add_column("users", sa.Column("email", sa.String(length=320), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(length=32), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "notify_by_email", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "users",
        sa.Column("notify_by_sms", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "notification_id",
            sa.Integer(),
            sa.ForeignKey("notifications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", delivery_channel, nullable=False),
        sa.Column("recipient", sa.String(length=320), nullable=False),
        sa.Column("status", delivery_status, nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # جارو فقط دنبال ردیف‌های در انتظار می‌گردد، به ترتیب قدمت.
    op.create_index(
        "ix_deliveries_pending", "notification_deliveries", ["status", "created_at"]
    )
    op.create_index(
        "ix_deliveries_notification", "notification_deliveries", ["notification_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_deliveries_notification", table_name="notification_deliveries")
    op.drop_index("ix_deliveries_pending", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
    op.drop_column("users", "notify_by_sms")
    op.drop_column("users", "notify_by_email")
    op.drop_column("users", "phone")
    op.drop_column("users", "email")
    postgresql.ENUM(name="delivery_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="delivery_channel").drop(op.get_bind(), checkfirst=True)
