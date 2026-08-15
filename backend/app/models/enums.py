import enum


class PersonnelStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class UserRole(str, enum.Enum):
    unit_supervisor = "unit_supervisor"
    hr = "hr"
    deputy = "deputy"
    ceo = "ceo"
    # کارمند عادی: فقط نتیجه نهایی ارزیابی خودش را می‌بیند و «رؤیت» می‌زند
    employee = "employee"


class IndicatorSection(str, enum.Enum):
    general = "general"
    specialized = "specialized"


class EvaluationStage(str, enum.Enum):
    supervisor_scoring = "supervisor_scoring"
    hr_review = "hr_review"
    deputy_review = "deputy_review"
    ceo_final = "ceo_final"


class EvaluationStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    hr_approved = "hr_approved"
    deputy_approved = "deputy_approved"
    finalized = "finalized"
    # وضعیت پایانی دوم: پرونده‌ای که به هر دلیل (خروج تأییدکننده، تخصیص اشتباه،
    # استعفای پرسنل) نباید ادامه پیدا کند. بدون این، تنها راه خروج از یک پروندهٔ
    # گیرکرده SQL دستی روی پروداکشن بود.
    cancelled = "cancelled"


class CommentStage(str, enum.Enum):
    hr_review = "hr_review"
    deputy_review = "deputy_review"
    ceo_final = "ceo_final"


class PeriodStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class ImprovementPlanStatus(str, enum.Enum):
    open = "open"
    completed = "completed"
    cancelled = "cancelled"


class SchemeStatus(str, enum.Enum):
    """چرخهٔ عمر یک طرح نمره‌دهی (P1-04).

    `active` عمداً بازگشت‌پذیر نیست: برای عوض کردن قواعد باید نسخهٔ تازه ساخت.
    ویرایش درجای یک نسخهٔ فعال، معنای پرونده‌های گذشته را بازنویسی می‌کند.
    """

    draft = "draft"
    active = "active"
    retired = "retired"


class DeliveryChannel(str, enum.Enum):
    """کانال‌های تحویل بیرونی (P1-03)."""

    email = "email"
    sms = "sms"


class DeliveryStatus(str, enum.Enum):
    """وضعیت یک ارسال در صندوق خروجی.

    `failed` و `abandoned` عمداً جدا هستند: اولی یعنی «دوباره تلاش می‌شود»،
    دومی یعنی «دیگر تلاش نمی‌شود و کسی باید نگاهش کند». یکی‌کردنشان یعنی صف پر
    از ردیف‌هایی می‌شود که هرگز نمی‌روند و هیچ‌کس خبردار نمی‌شود.
    """

    pending = "pending"
    sent = "sent"
    failed = "failed"
    abandoned = "abandoned"
