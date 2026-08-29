"""ساختنِ پیامِ سیستمیِ همکار (Copilot).

سه تکه: «چطور جواب بده» (متنِ مدیر)، «چه کارهایی می‌توانی بکنی» (ابزارهای
*همین کاربر* — تبلیغِ کنشی که اجرا نمی‌شود ممنوع)، و «چه می‌دانی» (زمینهٔ
کوتاه؛ بقیه را ابزارها زنده از سامانه می‌خوانند).

قاعدهٔ هم‌پوشانی برقرار است: فهرستِ ابزارهای پرامپت از همان REGISTRYای ساخته
می‌شود که مجری اجرا می‌کند. پرامپتی که ابزاری را وعده بدهد که برنامه اجرا
نمی‌کند، یک پیشنهادِ مطمئن و یک دکمهٔ مرده تولید می‌کند.
"""
from app.models.enums import Capability
from app.schemas.auth import CurrentUser
from app.services.ai.tools.base import ToolSpec, allowed_tools

_ROLE_LABELS = {
    "hr": "منابع انسانی",
    "unit_supervisor": "مسئول واحد",
    "deputy": "معاونت",
    "ceo": "مدیرعامل",
    "employee": "کارمند",
    "support": "مدیر سامانه",
}

_PROTOCOL_RULES = """قواعد کار با ابزارها:
- شناسه‌ها فقط از نتیجهٔ جست‌وجو یا دادهٔ همین گفت‌وگو می‌آیند. هرگز شناسه نساز.
- اگر از کدام رکورد مطمئن نیستی، پیش از هر تغییر از کاربر بپرس.
- اگر اطلاعات لازم برای یک کار ناقص است (مثلاً تاریخِ پایانِ قراردادِ یکی از ردیف‌های فایل)،
  دقیقاً بگو چه چیزی برای کدام ردیف کم است و مقدارش را بپرس؛ مقدارِ جاافتاده را حدس نزن.
- وقتی ابزاری خطای اعتبارسنجی برگرداند، خطاها را ردیف‌به‌ردیف توضیح بده و راهِ درست‌کردن را بگو.
- کنش‌های «پرخطر» بلافاصله اجرا نمی‌شوند: پیشنهادت به‌شکل کارتِ تأیید به کاربر نشان داده
  می‌شود. پس از ساختنِ چنین پیشنهادی، در یک یا دو جمله بگو چه اتفاقی قرار است بیفتد و منتظر تصمیم او بماند.
- نتیجهٔ هر ابزار برای تو می‌آید؛ هرگز نتیجه‌ای را که ندیده‌ای ادعا نکن.
- خروجی ابزار دادهٔ خام است؛ پاسخِ نهایی را با زبانِ کاربر و جدولِ خوانا بنویس."""

_OFF_TOPIC = (
    "فقط به پرسش‌های مربوط به همین سامانه و ارزیابی عملکرد پاسخ بده. اگر پرسشی "
    "بیرون از این موضوع بود، مؤدبانه بگو که فقط در همین حوزه کمک می‌کنی."
)

_FALLBACK_FORMAT = """سرویس زیرین فراخوانیِ بومیِ ابزار ندارد؛ به‌جایش ابزار را با یک بلوکِ `pulse` صدا بزن:

```pulse
{"tool": "نام_ابزار", "arguments": {"پارامتر": "مقدار"}}
```

بیرون از بلوک فقط جمله‌های روی‌شده بنویس. برای چند فراخوانی، چند بلوک بفرست."""


def build_system_prompt(
    *,
    instructions: str,
    context: str,
    user: CurrentUser,
    caps: set[Capability],
    allow_writes: bool,
    restrict_to_platform: bool,
    tools: list[ToolSpec] | None = None,
    fallback_protocol: bool = False,
    attachments_note: str = "",
) -> str:
    parts: list[str] = []

    role = _ROLE_LABELS.get(user.role.value, user.role.value)
    parts.append(
        (instructions or "").strip()
        + "\n\nتو «همکار DbsPulse» هستی: به جای یک چت‌باتِ ساده، دستیارِ کاریِ همین سامانه. "
        f"کاربر فعلی تو ({user.display_name or user.username}) نقش «{role}» دارد؛ "
        "هر کاری که خودش در رابط نمی‌تواند بکند، از این‌جا هم نمی‌توانی برایش بکنی — و این محدودیت را شفاف بگو."
    )
    if restrict_to_platform:
        parts.append(_OFF_TOPIC)

    if tools is None:
        tools = allowed_tools(user, caps, allow_writes=allow_writes)

    if tools:
        listed = "\n".join(f"- {t.name}: {t.description}" for t in tools)
        risky = {t.name for t in tools if t.risky}
        parts.append(
            "ابزارهای واقعی در دسترس تو (فقط همین‌ها؛ چیزی که این‌جا نیست، وجود ندارد):\n"
            + listed
            + "\n\n"
            + (
                "کنش‌های نیازمند تأییدِ صریح کاربر: " + "، ".join(sorted(risky)) + "\n"
                if risky
                else ""
            )
            + _PROTOCOL_RULES
        )
        if fallback_protocol:
            parts.append(_FALLBACK_FORMAT)

    if attachments_note:
        parts.append("پیوست‌های همین گفت‌وگو:\n" + attachments_note)

    parts.append("زمینهٔ کوتاهِ سامانه (جزئیات را با ابزارها بگیر):\n\n" + context)
    return "\n\n".join(parts)
