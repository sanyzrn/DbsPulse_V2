#!/bin/sh
set -e

echo "در حال اجرای migration های دیتابیس..."
alembic upgrade head

if [ "$#" -eq 0 ]; then
  # پشت reverse proxy (کانتینر frontend/Nginx)، IP واقعی کلاینت از X-Forwarded-For
  # می‌آید؛ بدون --proxy-headers محدودیت نرخ ورود برای کل سازمان یک سطل مشترک می‌شود.
  # در استقرار واقعی FORWARDED_ALLOW_IPS را به IP/شبکه پروکسی محدود کنید (پیش‌فرض *
  # فقط تا وقتی امن است که پورت backend مستقیماً در معرض اینترنت نباشد).
  exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
    --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}"
else
  exec "$@"
fi
