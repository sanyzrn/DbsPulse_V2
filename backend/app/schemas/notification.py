from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    message: str
    link: str | None
    evaluation_record_id: int | None
    created_at: datetime
    read_at: datetime | None


class NotificationPage(BaseModel):
    total: int
    unread: int
    items: list[NotificationRead]


class ExpiringContract(BaseModel):
    personnel_id: int
    full_name: str
    org_unit: str
    contract_end_date: date
    days_remaining: int
    has_open_evaluation: bool


class NotificationPreferences(BaseModel):
    """ارجحیت تماس کاربر برای اعلان‌های بیرونی (P1-03)."""

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)
    notify_by_email: bool = False
    notify_by_sms: bool = False


class NotificationPreferencesRead(NotificationPreferences):
    """همان ارجحیت‌ها، به‌علاوهٔ اینکه سازمان اصلاً کدام کانال را تنظیم کرده.

    بدون این، فرم به کاربر تیکی نشان می‌دهد که روشن‌کردنش هیچ اثری ندارد — و
    کاربر منتظر پیامی می‌ماند که هرگز قرار نبوده بیاید.
    """

    email_available: bool
    sms_available: bool


class DeliveryRow(BaseModel):
    """یک ردیف صندوق خروجی، برای عیب‌یابی."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    channel: str
    recipient: str
    status: str
    attempts: int
    last_error: str | None
    last_attempt_at: datetime | None
    sent_at: datetime | None
    created_at: datetime


class DeliveryQueueSummary(BaseModel):
    """وضعیت صف تحویل — «چه چیزی نرفت و چرا».

    بدون این، اعلانی که نرسیده هیچ ردی ندارد و «چرا فلانی خبردار نشد؟» بی‌جواب
    می‌ماند.
    """

    channels_configured: list[str]
    counts: dict[str, int]
    #: تازه‌ترین ردیف‌هایی که نرفته‌اند — همان‌هایی که کسی باید نگاهشان کند
    recent_problems: list[DeliveryRow]
