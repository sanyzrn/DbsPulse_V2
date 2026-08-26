"""سرویس‌های آمادهٔ دستیار.

چرا فهرست آماده و نه فقط یک فیلد آزاد
--------------------------------------
تا امروز مدیر باید «آدرس سرویس» را از حفظ می‌نوشت. نیمی از مشکلات راه‌اندازی
همین‌جا بود: یک `/v1` جامانده یا یک `https://` اشتباه، و پیام خطایی که دربارهٔ
آدرس چیزی نمی‌گفت. حالا یک کلیک آدرس و یک مدلِ پیش‌فرضِ سالم را می‌گذارد، و
«سفارشی» برای هر چیز دیگری سر جایش می‌ماند.

چرا همه از یک آداپتور رد می‌شوند
---------------------------------
Anthropic و Gemini هرکدام API بومیِ خودشان را دارند که با OpenAI فرق می‌کند.
ولی هر دو یک نقطهٔ پایانیِ *سازگار با OpenAI* هم منتشر می‌کنند، و آدرس‌های زیر
همان‌ها هستند. یعنی یک آداپتور، پنج سرویس — به‌جای پنج آداپتور که هرکدام باید
جدا نگه‌داری و تست شوند.

هزینه‌اش را هم صریح می‌گوییم: لایهٔ سازگاری را خودِ آن شرکت‌ها نگه می‌دارند و
گاهی از API بومی‌شان عقب‌تر است. برای کاری که این دستیار می‌کند — پرسش و پاسخ
متنی — تفاوتی ندارد.

مدلِ پیش‌فرض یک *پیشنهاد* است و در فرم قابل ویرایش می‌ماند: نام مدل‌ها سریع عوض
می‌شوند و قفل‌کردنشان در کد یعنی هر تغییرِ آن‌ها یک استقرارِ تازه.
"""
from dataclasses import dataclass

#: شناسهٔ سرویسِ «هر آدرسِ دیگر». عمداً مقدارِ پیش‌فرض است تا نصب‌های موجود که
#: آدرس را دستی نوشته‌اند، همان‌طور بمانند.
CUSTOM = "custom"


@dataclass(frozen=True)
class AiProvider:
    id: str
    label: str
    base_url: str
    default_model: str
    note: str = ""


PROVIDERS: tuple[AiProvider, ...] = (
    AiProvider(
        "anthropic",
        "Anthropic (Claude)",
        "https://api.anthropic.com/v1",
        "claude-sonnet-5",
        "از لایهٔ سازگار با OpenAI خودِ Anthropic استفاده می‌شود",
    ),
    AiProvider(
        "openai",
        "OpenAI",
        "https://api.openai.com/v1",
        "gpt-4o-mini",
    ),
    AiProvider(
        "gemini",
        "Google Gemini",
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "gemini-2.0-flash",
        "از نقطهٔ پایانیِ سازگار با OpenAI خودِ Google استفاده می‌شود",
    ),
    AiProvider(
        "openrouter",
        "OpenRouter",
        "https://openrouter.ai/api/v1",
        "openai/gpt-4o-mini",
        "یک کلید، دسترسی به مدل‌های چند شرکت",
    ),
    AiProvider(
        CUSTOM,
        "سفارشی (سازگار با OpenAI)",
        "",
        "",
        "آدرس و نام مدل را خودتان وارد کنید",
    ),
)

PROVIDERS_BY_ID = {provider.id: provider for provider in PROVIDERS}
