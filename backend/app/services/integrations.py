"""خواندن و نوشتنِ تنظیمات ارسال بیرونی، با اولویت دیتابیس بر `.env`.

چرا مقدارها روی خودِ `settings` نوشته می‌شوند
---------------------------------------------
کانال‌ها (`services/channels/*`) در لحظهٔ ارسال از `settings` می‌خوانند و هیچ
نشست دیتابیسی در دست ندارند. سه راه بود: نشست را تا داخل کانال‌ها ببریم (یعنی
دست‌زدن به قرارداد هر سه کانال برای چیزی که ربطی به کارشان ندارد)، یک لایهٔ
پیکربندی موازی بسازیم (یعنی دو منبع حقیقت)، یا همان مقدارها را روی همان شیئی
بنویسیم که کانال‌ها از آن می‌خوانند.

سومی انتخاب شد. `settings` از قبل هم در همین مخزن نوشتنی است — تست‌ها برای
خاموش‌کردن سرکوب کوهورت دقیقاً همین کار را می‌کنند — پس الگوی تازه‌ای نیست.

`refresh` در استارت‌آپ و پس از هر ذخیره صدا زده می‌شود؛ بین این دو، هیچ خواندنی
از دیتابیس روی مسیر ارسال نیست.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.integrations import EDITABLE_BY_KEY, SECRET_KEYS
from app.models.integration import IntegrationSetting

#: مقدارهای اولیهٔ `.env`، پیش از هر بازنویسی. بدون این، پاک‌کردن یک مقدار در
#: پنل نمی‌توانست به «همان چیزی که در .env بود» برگردد — چون آن مقدار دیگر
#: هیچ‌جا نبود.
_ENV_DEFAULTS: dict[str, object] = {key: getattr(settings, key) for key in EDITABLE_BY_KEY}


def _parse(key: str, raw: str) -> object:
    kind = EDITABLE_BY_KEY[key].kind
    if kind == "number":
        return int(raw)
    if kind == "bool":
        return raw == "true"
    return raw


def _serialise(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def stored_values(db: Session) -> dict[str, str]:
    return {
        row.key: row.value
        for row in db.scalars(select(IntegrationSetting))
        if row.key in EDITABLE_BY_KEY
    }


def effective_values(db: Session) -> dict[str, object]:
    """آنچه واقعاً اثر دارد: مقدار دیتابیس اگر باشد، وگرنه مقدار `.env`."""
    values = dict(_ENV_DEFAULTS)
    for key, raw in stored_values(db).items():
        try:
            values[key] = _parse(key, raw)
        except ValueError:
            # ردیف خرابِ دیتابیس نباید کل تنظیمات را از کار بیندازد؛ همان
            # مقدار `.env` می‌ماند و پنل تفاوت را نشان می‌دهد.
            continue
    return values


def refresh(db: Session) -> None:
    """مقدارهای مؤثر را روی `settings` می‌نشاند تا کانال‌ها همان را ببینند."""
    for key, value in effective_values(db).items():
        setattr(settings, key, value)


def save(db: Session, values: dict[str, object]) -> None:
    """فقط کلیدهای مجاز نوشته می‌شوند.

    allowlist بودنش عمدی است: بدون آن، یک کلید دلخواه در بدنهٔ درخواست می‌توانست
    هر صفتی از `settings` را بازنویسی کند — از جمله رمز دیتابیس.
    """
    for key, value in values.items():
        if key not in EDITABLE_BY_KEY:
            continue
        row = db.get(IntegrationSetting, key)
        if row is None:
            db.add(IntegrationSetting(key=key, value=_serialise(value)))
        else:
            row.value = _serialise(value)


def secret_status() -> dict[str, bool]:
    """فقط «تنظیم شده یا نه» — هرگز خودِ مقدار."""
    return {key: bool(getattr(settings, key, "")) for key, _ in SECRET_KEYS}
