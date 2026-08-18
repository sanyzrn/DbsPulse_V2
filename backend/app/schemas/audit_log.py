from datetime import datetime

from pydantic import BaseModel


class AuditLogRead(BaseModel):
    id: int
    evaluation_record_id: int | None
    evaluation_code: str | None
    actor_user_id: int
    actor_username: str | None
    # نامِ آدم، اگر ثبت شده باشد؛ وگرنه همان نام کاربری. UI نباید خودش این
    # جایگزینی را انجام بدهد و در هر صفحه یک‌جور بنویسدش.
    actor_display_name: str | None = None
    event_type: str
    old_value: dict | None
    new_value: dict | None
    created_at: datetime


class AuditLogPage(BaseModel):
    total: int
    items: list[AuditLogRead]


class AuditIntegrityRead(BaseModel):
    """نتیجهٔ راستی‌آزمایی زنجیرهٔ هش لاگ حسابرسی.

    broken_at_id عمداً فقط *اولین* ردیف ناسازگار است: از نقطهٔ شکست به بعد همهٔ
    حلقه‌ها می‌شکنند، پس فهرست‌کردن همه‌شان نویز است و آن‌چه باید بررسی شود همان اولی.
    """

    ok: bool
    checked: int
    broken_at_id: int | None
    reason: str | None
