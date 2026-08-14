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
    # از وقتی رندر PDF از مسیر درخواستِ نهایی‌سازی بیرون رفته (P2-05)، یک پنجرهٔ
    # کوتاه هست که پرونده نهایی شده ولی سند هنوز ساخته نشده. در آن پنجره sha256
    # خالی است — و «هشِ خالی» روی یک صفحهٔ *تأیید اصالت* از «سند دستکاری شده»
    # قابل تشخیص نیست. این پرچم آن دو را از هم جدا می‌کند.
    document_ready: bool = True
