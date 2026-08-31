"""تنظیمات سرویس‌های ارسال بیرونی — کدام‌شان از پنل عوض می‌شوند و کدام نه.

چرا دو دسته
-----------
کل موتور ارسال (صف، تلاش مجدد، جداکردن خطای دائمی از گذرا) از قبل ساخته شده
بود، ولی هیچ جایی برای *وارد کردن* تنظیماتش وجود نداشت جز فایل `.env` روی سرور.
یعنی عوض‌کردن قالب پیامک به دسترسی SSH نیاز داشت.

ولی همه‌چیز را هم نمی‌شود به دیتابیس برد: رمز SMTP و کلید API اگر آن‌جا بنشینند،
در هر بک‌آپی هم می‌نشینند — و بک‌آپ دیتابیس معمولاً جاهایی می‌رود که فایل `.env`
نمی‌رود.

پس تقسیم بر اساس همین است: هر چیزی که *افشایش* هزینه دارد در `.env` می‌ماند و
پنل فقط می‌گوید تنظیم شده یا نه؛ بقیه — آدرس، پورت، قالب پیام — از پنل قابل
ویرایش‌اند، چون همان‌هایی‌اند که واقعاً عوض می‌شوند.

فهرست معتبرها این‌جاست و نه در دیتابیس، به همان دلیلِ `core/modules.py`: یک ردیف
با کلید اشتباه یعنی تنظیمی که هیچ کدی نمی‌خواندش.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class IntegrationField:
    #: نامش دقیقاً همان صفتِ `Settings` است؛ نگاشت دوم یعنی جایی از هم دور می‌افتند.
    key: str
    label: str
    #: "text" | "number" | "bool"
    kind: str
    help: str = ""
    #: کف و سقفِ عددی. یک «حد نمایش کوهورت» صفر یعنی خاموش‌کردنِ بی‌سروصدای
    #: ناشناس‌ماندن، و یک «مهلت اعتراض» منفی یعنی پنجره‌ای که هیچ‌وقت باز نیست.
    minimum: int | None = None
    maximum: int | None = None


#: قابل ویرایش از پنل. هیچ‌کدام رمز نیستند.
EDITABLE: tuple[IntegrationField, ...] = (
    IntegrationField("smtp_host", "میزبان SMTP", "text", "خالی یعنی ایمیل خاموش است"),
    IntegrationField("smtp_port", "پورت SMTP", "number"),
    IntegrationField("smtp_from", "فرستنده", "text", "نشانی‌ای که گیرنده می‌بیند"),
    IntegrationField("smtp_use_starttls", "STARTTLS", "bool"),
    IntegrationField("smtp_use_ssl", "SSL مستقیم", "bool"),
    IntegrationField("sms_url", "آدرس سرویس پیامک", "text", "خالی یعنی پیامک خاموش است"),
    IntegrationField("sms_method", "متد HTTP", "text", "معمولاً POST یا GET"),
    IntegrationField("sms_headers", "هدرها", "text", "هر خط یک هدر: Name: value"),
    IntegrationField("sms_body", "بدنهٔ درخواست", "text", "{recipient} و {message} جایگزین می‌شوند"),
    IntegrationField(
        "sms_success_contains",
        "نشانهٔ موفقیت در پاسخ",
        "text",
        "اگر سرویس روی خطا هم ۲۰۰ می‌دهد، این رشته باید در پاسخِ موفق باشد",
    ),
)

#: فقط از `.env` خوانده می‌شوند. پنل نشان می‌دهد تنظیم شده‌اند یا نه — و هرگز
#: مقدارشان را برنمی‌گرداند.
SECRET_KEYS: tuple[tuple[str, str], ...] = (
    ("smtp_username", "نام کاربری SMTP"),
    ("smtp_password", "رمز SMTP"),
    ("sms_api_key", "کلید API پیامک"),
)

#: قاعده‌های سازمانی — عددهایی که تا امروز فقط در `.env` بودند.
#:
#: این‌ها نه راز‌اند و نه فنی: «چند روز مهلت اعتراض» و «از چند نفر به بالا
#: میانگین را نشان بده» تصمیم‌های سازمان‌اند، نه تصمیم‌های استقرار. تا امروز
#: عوض‌کردنشان به دسترسی SSH نیاز داشت.
#:
#: عمداً هر عددی به این فهرست نیامده: اندازهٔ استخر اتصال و مهلت توکن، تصمیم
#: استقرارند و جایشان همان `.env` است.
POLICY: tuple[IntegrationField, ...] = (
    IntegrationField(
        "objection_window_days",
        "مهلت اعتراض کارمند (روز)",
        "number",
        "از لحظهٔ نهایی‌شدن پرونده، کارمند چند روز برای ثبت اعتراض دارد",
        minimum=1,
        maximum=365,
    ),
    IntegrationField(
        "min_cohort_size",
        "حداقل جمعیت برای نمایش میانگین",
        "number",
        "میانگینِ گروهی که کمتر از این تعداد باشد نشان داده نمی‌شود، تا امتیاز فرد از آن بیرون نیاید",
        minimum=1,
        maximum=100,
    ),
    IntegrationField(
        "contract_expiry_alert_days",
        "هشدار پایان قرارداد (روز)",
        "number",
        "چند روز پیش از پایان قرارداد، منابع انسانی خبردار شود",
        minimum=1,
        maximum=365,
    ),
    IntegrationField(
        "sla_reminder_days",
        "یادآوری پروندهٔ راکد (روز)",
        "number",
        "پرونده‌ای که این تعداد روز در یک مرحله بماند، به مسئولش یادآوری می‌شود",
        minimum=1,
        maximum=90,
    ),
    IntegrationField(
        "improvement_review_alert_days",
        "یادآوری بازبینی برنامهٔ بهبود (روز)",
        "number",
        "چند روز پیش از موعد بازبینی، یادآوری فرستاده شود",
        minimum=1,
        maximum=90,
    ),
    IntegrationField(
        "notification_dedup_days",
        "فاصلهٔ تکرار یک اعلان (روز)",
        "number",
        "همان اعلان برای همان پرونده، زودتر از این فاصله دوباره فرستاده نمی‌شود",
        minimum=1,
        maximum=90,
    ),
    IntegrationField(
        "login_max_failed_attempts",
        "تعداد ورود ناموفق تا قفل‌شدن",
        "number",
        "بعد از این تعداد تلاش ناموفق، حساب موقتاً قفل می‌شود",
        minimum=3,
        maximum=50,
    ),
    IntegrationField(
        "login_lockout_minutes",
        "مدت قفل‌شدن حساب (دقیقه)",
        "number",
        "حسابِ قفل‌شده پس از این مدت خودبه‌خود باز می‌شود",
        minimum=1,
        maximum=1440,
    ),
)

#: allowlistِ نوشتن. اتحادِ دو گروه است، ولی هر نقطهٔ ورودی فقط کلیدهای گروهِ
#: خودش را می‌فرستد — وگرنه صفحهٔ «ایمیل و پیامک» می‌توانست مهلت اعتراض را هم
#: عوض کند.
EDITABLE_BY_KEY = {field.key: field for field in (*EDITABLE, *POLICY)}
