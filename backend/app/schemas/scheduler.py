from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SchedulerRunRead(BaseModel):
    """یک اجرای کارهای زمان‌بندی‌شده.

    status یکی از: succeeded | failed | skipped_locked.
    skipped_locked خطا نیست — یعنی instance دیگری رهبر بود و این یکی درست عمل کرده
    که کار را دوباره انجام نداده.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    finished_at: datetime | None
    status: str
    trigger: str
    summary: dict | None
    error: str | None
