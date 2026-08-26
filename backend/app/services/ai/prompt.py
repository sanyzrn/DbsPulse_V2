"""ساختنِ پیامِ سیستمی.

سه تکه: «چطور جواب بده» (متنِ مدیر)، «چه کنش‌هایی مجازند» (از روی دسترسیِ همین
کاربر)، و «چه می‌دانی» (زمینه).

فهرست کنش‌ها از `actions.REQUIREMENTS` ساخته می‌شود و نه دستی، تا هر کنشی که در
پرامپت تبلیغ می‌شود در تجزیه‌کننده و مجری هم وجود داشته باشد. تستِ
`test_ai_actions` همین را ادعا می‌کند: پرامپتی که کنشی را وعده بدهد که برنامه
اجرا نمی‌کند، یک پیشنهادِ مطمئن و یک دکمهٔ مرده تولید می‌کند.
"""
from app.models.enums import Capability
from app.schemas.auth import CurrentUser
from app.services.ai.actions import allowed_actions

_SHAPES: dict[str, str] = {
    "find": '{"action": "find", "query": "<چه چیزی را می‌جویی>"}',
    "create_personnel": (
        '{"action": "create_personnel", "full_name": "<نام کامل>", "personnel_code": "<کد>", '
        '"job_title": "<عنوان شغلی>", "org_unit": "<واحد>", "contract_end_date": "YYYY-MM-DD"}'
    ),
    "update_personnel": '{"action": "update_personnel", "id": <شناسه>, "fields": {"job_title": "<...>"}}',
    "create_org_unit": '{"action": "create_org_unit", "name": "<نام واحد>", "site": "<محل یا خالی>"}',
    "invite_self_assessment": '{"action": "invite_self_assessment", "personnel_id": <شناسه>}',
    "deactivate_user": '{"action": "deactivate_user", "user_id": <شناسه>}',
}

_RULES = """قواعد کنش‌ها:
- بیرون از بلوک چیزی ننویس؛ برنامه پیشنهادت را به کاربر نشان می‌دهد و منتظر تأیید
  او می‌ماند، پس هر جمله‌ای دور بلوک خوانده نمی‌شود.
- وقتی یک خواسته واقعاً چند تغییر لازم دارد، چند بلوک بفرست؛ همه با هم تأیید می‌شوند.
- شناسه‌ها فقط از فهرست زیر یا از نتیجهٔ جست‌وجو می‌آیند. هرگز شناسه نساز.
- اگر مطمئن نیستی کدام رکورد منظور است، به‌جای حدس‌زدن بپرس.
- برای هر چیزی که *پرسش* است و نه درخواستِ تغییر، عادی جواب بده و هیچ بلوکی نگذار."""

_OFF_TOPIC = (
    "فقط به پرسش‌های مربوط به همین سامانه و ارزیابی عملکرد پاسخ بده. اگر پرسشی "
    "بیرون از این موضوع بود، مؤدبانه بگو که فقط در همین حوزه کمک می‌کنی."
)


def build_system_prompt(
    *,
    instructions: str,
    context: str,
    user: CurrentUser,
    caps: set[Capability],
    allow_writes: bool,
    restrict_to_platform: bool,
) -> str:
    parts = [instructions.strip()]
    if restrict_to_platform:
        parts.append(_OFF_TOPIC)

    names = allowed_actions(user, caps)
    if not allow_writes:
        # فقط خواندنی‌ها می‌مانند — یعنی `find`.
        names = [n for n in names if n == "find"]

    if names:
        shapes = "\n".join(f"```pulse\n{_SHAPES[name]}\n```" for name in names if name in _SHAPES)
        parts.append(
            "می‌توانی روی دادهٔ سامانه کنش پیشنهاد بدهی. برای این کار فقط یک بلوکِ "
            "`pulse` با یک شیء JSON بنویس:\n\n" + shapes + "\n\n" + _RULES
        )

    parts.append("داده‌های در دسترس تو:\n\n" + context)
    return "\n\n".join(parts)
