from datetime import datetime

from pydantic import BaseModel


class VerificationResult(BaseModel):
    """پاسخ عمومی تأیید اصالت سند (بدون احراز هویت). فقط داده‌های لازم برای تأیید،
    نه جزئیات حساس مثل شواهد یا کامنت‌ها."""

    valid: bool
    evaluation_code: str
    subject_full_name: str
    org_unit: str
    final_weighted_pct: float | None
    recommendation: str | None
    finalized_at: datetime | None
    sha256: str
