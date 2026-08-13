"""محدودیت نرخِ per-IP — لایهٔ اول دفاع در برابر brute-force.

لایهٔ دوم (قفل حساب بر اساس نام کاربری) در services/login_guard.py است و همیشه در
دیتابیس مشترک می‌ماند. این دو مکمل‌اند: per-IP جلوی یک مهاجم پرسرعت را می‌گیرد،
per-username جلوی حملهٔ توزیع‌شده و آهسته روی یک حساب مشخص را.

storage_uri خالی یعنی حافظهٔ درون‌پروسه: با N کارگر هر محدودیت عملاً N برابر می‌شود
و ری‌استارت پاکش می‌کند. برای استقرار چندنسخه‌ای RATE_LIMIT_STORAGE_URI را به یک
backend مشترک (مثلاً redis://redis:6379) بدهید — بدون تغییر کد.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

_storage_uri = settings.rate_limit_storage_uri.strip()

limiter = Limiter(
    key_func=get_remote_address,
    **({"storage_uri": _storage_uri} if _storage_uri else {}),
)
