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

EDITABLE_BY_KEY = {field.key: field for field in EDITABLE}
