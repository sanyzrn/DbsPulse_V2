"""audit hash chain

P1-09 — لاگ حسابرسی باید مدرک باشد، نه مستندات.

پیش از این هیچ‌چیز جلوی UPDATE/DELETE روی audit_log را نمی‌گرفت، پس لاگ فقط برای
کسی که از قبل به دارندهٔ دسترسی دیتابیس اعتماد دارد چیزی را ثابت می‌کرد — و طبق
P0-03 همان نقشی که لاگ قرار بود پاسخ‌گو نگهش دارد، این دسترسی را دارد.

دو لایه: ستون‌های زنجیرهٔ هش (backfill می‌شوند تا ردیف‌های موجود هم در زنجیره
بیایند) و تریگری که تغییر و حذف را رد می‌کند.

تریگر به‌جای REVOKE: این استقرار یک نقش دیتابیس بیشتر ندارد — همان نقشی که
مایگریشن‌ها را اجرا می‌کند — پس REVOKE عملاً چیزی را نمی‌بست.

Revision ID: e8f4b127d905
Revises: d2f75a9c31e8
Create Date: 2026-08-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e8f4b127d905'
down_revision: Union[str, None] = 'd2f75a9c31e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GUARD = """
CREATE OR REPLACE FUNCTION forbid_audit_log_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'audit_log is append-only: % is not permitted', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.add_column("audit_log", sa.Column("prev_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_log", sa.Column("entry_hash", sa.String(length=64), nullable=True))

    # ردیف‌های موجود وارد زنجیره می‌شوند. این‌ها *گذشته* را اثبات نمی‌کنند — پیش از
    # وجود زنجیره نوشته شده‌اند — ولی از این نقطه به بعد هر تغییری در آن‌ها هم قابل
    # کشف می‌شود. زنجیره در پایتون ساخته می‌شود تا دقیقاً همان تابع هشِ services/audit.py
    # باشد؛ دو پیاده‌سازی موازی یعنی راستی‌آزمایی روزی بی‌دلیل شکست می‌خورد.
    from app.services.audit import GENESIS_HASH, compute_hash

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, actor_user_id, event_type, evaluation_record_id, old_value, new_value "
            "FROM audit_log ORDER BY id"
        )
    ).all()
    prev = GENESIS_HASH
    for row in rows:
        entry = compute_hash(
            actor_user_id=row.actor_user_id,
            event_type=row.event_type,
            evaluation_record_id=row.evaluation_record_id,
            old_value=row.old_value,
            new_value=row.new_value,
            prev_hash=prev,
        )
        conn.execute(
            sa.text("UPDATE audit_log SET prev_hash = :p, entry_hash = :e WHERE id = :i"),
            {"p": prev, "e": entry, "i": row.id},
        )
        prev = entry

    op.alter_column("audit_log", "prev_hash", nullable=False)
    op.alter_column("audit_log", "entry_hash", nullable=False)

    # تریگر *پس از* backfill ساخته می‌شود، وگرنه خودِ UPDATE های بالا را رد می‌کرد.
    op.execute(_GUARD)
    op.execute(
        "CREATE TRIGGER trg_audit_log_append_only "
        "BEFORE UPDATE OR DELETE ON audit_log "
        "FOR EACH ROW EXECUTE FUNCTION forbid_audit_log_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_append_only ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS forbid_audit_log_mutation()")
    op.drop_column("audit_log", "entry_hash")
    op.drop_column("audit_log", "prev_hash")
