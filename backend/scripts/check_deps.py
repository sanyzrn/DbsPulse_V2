"""آیا این venv واقعاً چیزی را که برنامه import می‌کند دارد؟

چرا این فایل هست
----------------
راه‌انداز برای این‌که هر بار pip را از نو اجرا نکند، یک کپی از
`requirements.txt` را کنار venv نگه می‌دارد و می‌گوید «اگر تغییر نکرده،
یعنی نصب است». ولی آن نشانه فقط می‌گوید *ما یک‌بار pip را اجرا کردیم* — نه
این‌که پکیج‌ها هنوز سر جایشان هستند. venv می‌تواند بدون این‌که نشانه عوض
شود پکیج از دست بدهد: pip نیمه‌کاره قطع شود، آنتی‌ویروس چیزی را قرنطینه
کند، یا پوشه نصفه پاک شود.

نتیجه‌اش دقیقاً همان چیزی بود که وقت زیادی گرفت: راه‌انداز می‌گفت
«packages already match»، یووی‌کورن در پنجرهٔ خودش با ModuleNotFoundError
می‌مرد، و فرانت‌اند فقط ECONNREFUSED نشان می‌داد — هیچ‌جا نمی‌گفت پکیج کم
است. وجود `uvicorn.exe` هم جواب نیست؛ آن می‌ماند در حالی که بقیه رفته‌اند.

پس این‌جا خودِ import را امتحان می‌کنیم و نامِ چیزی را که کم است می‌گوییم.

کدهای خروج
----------
۰  همه چیز قابل import است
۱  دست‌کم یک وابستگیِ الزامی import نمی‌شود (نام‌ها چاپ می‌شوند)

اجرا (از پوشهٔ backend)::

    python -m scripts.check_deps
"""
from __future__ import annotations

import importlib
import sys

# نگاشت «نام بسته در requirements.txt» → «نامی که import می‌شود».
# این دو همیشه یکی نیستند (PyJWT → jwt، argon2-cffi → argon2، ...)، پس
# نمی‌شود از روی requirements.txt حدسش زد. تست
# tests/test_dependency_probe.py می‌سنجد که این جدول از requirements.txt
# عقب نماند.
REQUIRED = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "sqlalchemy": "sqlalchemy",
    "alembic": "alembic",
    "psycopg": "psycopg",
    "pydantic": "pydantic",
    "pydantic-settings": "pydantic_settings",
    "PyJWT": "jwt",
    "argon2-cffi": "argon2",
    "python-multipart": "python_multipart",
    "jinja2": "jinja2",
    "slowapi": "slowapi",
    "jdatetime": "jdatetime",
    "prometheus-client": "prometheus_client",
    "openpyxl": "openpyxl",
    "qrcode": "qrcode",
    # رمزنگاریِ کلیدهای API دستیار پیش از ذخیره در دیتابیس. الزامی و نه
    # اختیاری: بدون آن هر خواندنِ تنظیمات دستیار در import شکست می‌خورد، نه
    # پشتِ یک try/except.
    "cryptography": "cryptography",
    # کلاینت سرویس دستیار در import روتر API لازم است؛ نبودنش کل بک‌اند را
    # پیش از bind شدن پورت متوقف می‌کند.
    "httpx": "httpx",
}

# اختیاری‌ها: نبودشان برنامه را زمین نمی‌زند، پس نباید راه‌اندازی را متوقف
# کنند. weasyprint در app/services/pdf.py پشت try/except وارد می‌شود و
# نبودش فقط یعنی «خروجی PDF نداریم».
OPTIONAL = {
    "weasyprint": "weasyprint",
}


def missing(modules: dict[str, str]) -> list[tuple[str, str]]:
    result = []
    for package, module in modules.items():
        try:
            importlib.import_module(module)
        except ImportError:
            result.append((package, module))
    return result


def main() -> int:
    gone = missing(REQUIRED)
    if gone:
        names = ", ".join(package for package, _ in gone)
        print(f"missing required packages: {names}", file=sys.stderr)
        return 1

    for package, _ in missing(OPTIONAL):
        print(f"note: optional package {package} is not installed (PDF export disabled)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
