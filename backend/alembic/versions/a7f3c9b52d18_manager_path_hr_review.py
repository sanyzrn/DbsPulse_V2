"""مرحلهٔ بررسی منابع انسانی در مسیر «مدیر»

ممیزی HR این را پیدا کرد و درست بود: پروندهٔ پرسنلِ علامت‌خورده به‌عنوان «مدیر»
مستقیماً در وضعیت `hr_approved` ساخته می‌شد. یعنی معاونت نمره می‌داد و **خودش
همان نمره را تأیید می‌کرد** و پرونده می‌رفت روی میز مدیرعامل — مرحلهٔ `submitted`،
همان مرحلهٔ بررسی منابع انسانی، در این مسیر هرگز رخ نمی‌داد.

نتیجه‌اش این بود که پروندهٔ مدیران — پرامدترین ارزیابی‌های سازمان — با **دو چشم**
بسته می‌شد، در حالی که پروندهٔ یک کارشناس با **چهار چشم**. دقیقاً برعکسِ چیزی که
باید باشد.

مسیر تازه از همان قطعه‌های موجود ساخته شده، بدون وضعیت جدید:

    draft (معاونت نمره می‌دهد) → submitted (منابع انسانی) → deputy_approved
    (مدیرعامل) → finalized

مرحلهٔ معاونت پریده می‌شود چون **انجام شده**، نه چون وجود ندارد — قرینهٔ همان
منطقی که برای زنجیرهٔ بی‌معاونت داریم.

## دادهٔ موجود

پروندهٔ بازِ مسیر «مدیر» در وضعیت `hr_approved` می‌ماند، که در معنای تازه یعنی
«منتظر تأیید معاونت» — و آن مرحله در این مسیر وجود ندارد، پس پرونده گیر می‌کرد.
به `draft` منتقل می‌شود: همان جایی که معاونت نمره‌اش را می‌دهد و بعد ثبت می‌کند.

شرطِ `unit_supervisor_user_id IS NULL` دقیقاً مسیر «مدیر» را می‌گیرد و هیچ
پروندهٔ مسیر عادی را لمس نمی‌کند.

Revision ID: a7f3c9b52d18
Revises: f4b81d29e6a7
Create Date: 2026-08-24
"""
import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger("alembic.runtime.migration")

revision: str = "a7f3c9b52d18"
down_revision: str | None = "f4b81d29e6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MOVE = sa.text(
    """
    UPDATE evaluation_records
       SET status = :to_status, stage_entered_at = now()
     WHERE status = :from_status
       AND unit_supervisor_user_id IS NULL
    """
)


def upgrade() -> None:
    result = op.get_bind().execute(
        _MOVE, {"from_status": "hr_approved", "to_status": "draft"}
    )
    if result.rowcount:
        logger.warning(
            "%d پروندهٔ بازِ مسیر «مدیر» به مرحلهٔ نمره‌دهی برگشت؛ معاونت باید آن را "
            "ثبت کند تا به بررسی منابع انسانی برود.",
            result.rowcount,
        )


def downgrade() -> None:
    # برگشت به رفتار قبلی: پروندهٔ در حال نمره‌دهیِ مسیر «مدیر» همان hr_approved بود.
    op.get_bind().execute(_MOVE, {"from_status": "draft", "to_status": "hr_approved"})
