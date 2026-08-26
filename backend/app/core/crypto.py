"""رمزنگاریِ متقارنِ رازهایی که ناچاریم در دیتابیس نگه داریم.

قاعدهٔ سامانه این بوده که راز در `.env` بماند و به دیتابیس نرود، چون بک‌آپِ
دیتابیس جاهایی می‌رود که `.env` نمی‌رود. کلیدهای API دستیار این قاعده را
نمی‌پذیرند: هر کاربر می‌تواند کلید خودش را داشته باشد، پس کلید به یک *ردیف*
گره خورده و جایش دیتابیس است.

راه‌حل، رمزکردنِ آن‌ها با کلیدی است که در `.env` می‌ماند. یعنی بک‌آپِ لو رفتهٔ
دیتابیس، به تنهایی هیچ کلید معتبری نمی‌دهد.

کلیدِ رمزنگاری از `AI_ENCRYPTION_KEY` می‌آید و اگر تنظیم نشده باشد از
`JWT_SECRET_KEY` مشتق می‌شود. دومی یک مصالحه است: اگر کلیدِ اختصاصی را الزامی
می‌کردیم، هر نصبِ موجود با یک خطای تازه بالا نمی‌آمد. عوض‌شدنِ `JWT_SECRET_KEY`
هم — که همهٔ نشست‌ها را باطل می‌کند — کلیدهای ذخیره‌شده را ناخوانا می‌کند؛
`decrypt` این حالت را به‌جای فروپاشی، «تنظیم نشده» گزارش می‌کند.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet() -> Fernet:
    raw = (getattr(settings, "ai_encryption_key", "") or settings.jwt_secret_key).encode()
    # Fernet یک کلیدِ ۳۲ بایتیِ base64 می‌خواهد؛ رشتهٔ دلخواه را با SHA-256 به
    # همان شکل می‌آوریم به‌جای اینکه از کاربر بخواهیم کلید base64 بسازد.
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(raw).digest()))


def encrypt(value: str) -> str:
    """رشتهٔ خالی خالی می‌ماند — «تنظیم نشده» یک مقدارِ رمزشده نیست."""
    if not value:
        return ""
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """ناخوانا = تنظیم‌نشده، نه خطا.

    اگر کلیدِ رمزنگاری عوض شده باشد، مقدارهای قدیمی باز نمی‌شوند. انتخاب بین
    «سامانه بالا نیاید» و «دستیار بگوید تنظیم نشده» است؛ دومی قابل رفع است و
    اولی نیست.
    """
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        return ""


def masked(value: str) -> str:
    """چیزی که به رابط برمی‌گردد: نشانه‌ای که آدم بشناسدش، نه خودِ کلید."""
    plain = decrypt(value)
    if not plain:
        return ""
    return f"…{plain[-4:]}" if len(plain) > 4 else "…"
