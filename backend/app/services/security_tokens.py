"""تولید رمز موقت سمت سرور.

جدا از فرانت است چون رمزِ ورود دسته‌ای را *سرور* می‌سازد: فرستادن صدها رمز از
مرورگر به سرور یعنی همان رازها یک بار اضافه از شبکه رد شوند، بی‌آن‌که چیزی
به‌دست بیاید.
"""
import secrets

# نویسه‌های مبهم (O/0، l/1/I) عمداً نیستند: این رمز را HR روی کاغذ یا در پیام به
# فرد می‌دهد و باید بدون اشتباه تایپ شود.
_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_SYMBOLS = "!@#$%^&*-_=+"


def generate_temp_password(length: int = 16) -> str:
    """رمز تصادفی قوی با secrets — نه random، که برای رمز قابل پیش‌بینی است."""
    body = "".join(secrets.choice(_ALPHABET) for _ in range(length - 1))
    # دست‌کم یک نماد، تا رمز تولیدی از سیاست‌های مرسوم هم رد شود
    symbol = secrets.choice(_SYMBOLS)
    position = secrets.randbelow(length)
    return body[:position] + symbol + body[position:]
