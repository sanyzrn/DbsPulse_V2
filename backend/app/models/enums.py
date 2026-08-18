import enum


class PersonnelStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class SeparationReason(str, enum.Enum):
    """چرا این فرد دیگر در سازمان نیست.

    «غیرفعال» به‌تنهایی کافی نبود. استعفا، اخراج، پایان قرارداد و بازنشستگی در
    هیچ گزارش منابع انسانی‌ای یک چیز نیستند — نرخ استعفا در یک واحد یک سیگنال
    است، پایان قرارداد یک برنامه‌ریزی. بدون ثبت علت، هر دو به یک ردیفِ خاموشِ
    یکسان تبدیل می‌شدند و تفاوتشان فقط در حافظهٔ کسی می‌ماند که آن روز آن‌جا بود.
    """

    resignation = "resignation"
    dismissal = "dismissal"
    contract_end = "contract_end"
    retirement = "retirement"
    other = "other"


class UserRole(str, enum.Enum):
    unit_supervisor = "unit_supervisor"
    hr = "hr"
    deputy = "deputy"
    ceo = "ceo"
    # کارمند عادی: فقط نتیجه نهایی ارزیابی خودش را می‌بیند و «رؤیت» می‌زند
    employee = "employee"
    # پشتیبانی فنی: *هیچ* جایی در زنجیرهٔ ارزیابی ندارد و در هیچ گاردِ گردش‌کاری
    # فهرست نشده — یعنی روی همهٔ آن‌ها به‌صورت پیش‌فرض ۴۰۳ می‌گیرد. اختیاراتش
    # فقط از مجوزهای اداری می‌آید (models/capability.py). کسی که سامانه را نگه
    # می‌دارد لازم نیست نمرهٔ کسی را ببیند.
    support = "support"


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


class Capability(str, enum.Enum):
    """اختیارات اداری، مستقل از نقش (نیمهٔ دوم P0-03).

    عمداً ریز است: «مدیر سامانه» یک مجوز نیست، چند مجوز است. یک مجوزِ همه‌کاره
    دقیقاً همان مشکلی را می‌سازد که این تفکیک برای حلش آمده.
    """

    #: ساخت، ویرایش و غیرفعال‌کردن حساب کاربری
    manage_users = "manage_users"
    #: دادن و گرفتنِ همین مجوزها — عمداً از `manage_users` جدا شد.
    #:
    #: تا پیش از این یکی بودند، و نتیجه‌اش این بود که هرکس می‌توانست حساب بسازد،
    #: می‌توانست به خودش هر اختیاری هم بدهد. یعنی تفکیک وظایف با یک کلیک از بین
    #: می‌رفت. حالا «حساب می‌سازم» و «اختیار می‌دهم» دو کار جدا هستند: منابع
    #: انسانی اولی را دارد چون کارِ روزمره‌اش است، دومی را ندارد.
    manage_capabilities = "manage_capabilities"
    #: شاخص‌های فرم ارزیابی و طرح نمره‌دهی
    manage_scoring = "manage_scoring"
    #: تنظیمات ایمیل/پیامک و آزمودن اتصال
    manage_integrations = "manage_integrations"
    #: خواندن *کل* لاگ ممیزی، شامل ردیف‌هایی که امتیاز و نتیجهٔ پرونده‌ها را در
    #: خود دارند. عمداً از `view_diagnostics` جداست: عیب‌یابیِ سامانه («چرا این
    #: حساب وارد نمی‌شود») به رویدادهای سامانه‌ای نیاز دارد، نه به نمرهٔ کسی.
    #: تا پیش از این، دسترسی به لاگ کامل به نقش `hr` گره خورده بود — یعنی همان
    #: کسی که در زنجیره تصمیم می‌گیرد، تنها کسی هم بود که می‌توانست ردِ تصمیم‌ها
    #: را بخواند. حالا یک مجوزِ صریح است که داده و گرفته می‌شود.
    view_audit_log = "view_audit_log"
    #: روشن و خاموش کردن بخش‌های سامانه
    manage_modules = "manage_modules"
    #: سلامت سامانه، صف تحویل، وضعیت مایگریشن — خواندنی
    view_diagnostics = "view_diagnostics"
