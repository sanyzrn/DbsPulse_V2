"""phase5 verify token

کد ارزیابی (EVL-0001, EVL-0002, ...) ترتیبی و قابل‌حدس است؛ اگر endpoint عمومی
تأیید اصالت (/api/verify/{code}) با همین کد جست‌وجو شود، هرکسی می‌تواند با شمارش
ساده کد، نام/واحد/نتیجهٔ همهٔ پرسنل را استخراج کند. این migration یک توکن تصادفی
و غیرقابل‌حدس (verify_token) اضافه می‌کند که فقط برای جست‌وجوی عمومی استفاده
می‌شود؛ evaluation_code همچنان برای جست‌وجوی داخلی HR باقی می‌ماند. توکن فقط در
لحظهٔ نهایی‌سازی (ceo_finalize) تولید می‌شود؛ ردیف‌های نهایی‌شدهٔ موجود همین‌جا
backfill می‌شوند تا سند/QR چاپی قدیمی هم بی‌اعتبار نشود... اما چون QR های چاپی
قبلی evaluation_code را در URL دارند، توکن جدید برایشان کار نمی‌کند مگر PDF
دوباره صادر شود؛ این تبعیض عمدی و مستند است (رجوع کنید به یادداشت در verify.py).

Revision ID: b28cc6abdf2a
Revises: f1c93b7ad025
Create Date: 2026-07-06

"""
import secrets
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b28cc6abdf2a'
down_revision: Union[str, None] = 'f1c93b7ad025'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'evaluation_records', sa.Column('verify_token', sa.String(length=64), nullable=True)
    )
    op.create_index(
        'ix_evaluation_records_verify_token',
        'evaluation_records',
        ['verify_token'],
        unique=True,
    )

    # backfill: هر ارزیابی نهایی‌شدهٔ موجود یک توکن تصادفی می‌گیرد تا صفحهٔ تأیید
    # همچنان برای اسناد قبلاً صادرشده کار کند (با فرض صدور دوبارهٔ PDF/QR)
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id FROM evaluation_records WHERE status = 'finalized' AND verify_token IS NULL"
        )
    ).fetchall()
    for (record_id,) in rows:
        conn.execute(
            sa.text("UPDATE evaluation_records SET verify_token = :token WHERE id = :id"),
            {"token": secrets.token_urlsafe(24), "id": record_id},
        )


def downgrade() -> None:
    op.drop_index('ix_evaluation_records_verify_token', table_name='evaluation_records')
    op.drop_column('evaluation_records', 'verify_token')
