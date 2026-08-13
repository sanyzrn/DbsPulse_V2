#!/bin/sh
set -e

# مایگریشن‌ها عمداً این‌جا اجرا نمی‌شوند.
#
# پیش از این هر بوت کانتینر «alembic upgrade head» می‌زد. دو مشکل داشت: در rollout
# چندنسخه‌ای چند پروسه هم‌زمان schema را عوض می‌کردند (race)، و تغییر schema به یک
# اتفاق ناخواستهٔ ضمنی تبدیل می‌شد نه یک تصمیم صریح. حالا سرویس جداگانهٔ `migrate`
# در docker-compose.yml این کار را یک‌بار و پیش از بالا آمدن بک‌اند انجام می‌دهد:
#
#   docker compose run --rm migrate
#
# entrypoint هر آرگومانی را exec می‌کند، پس همان ایمیج برای اجرای alembic هم کار می‌کند.

if [ "$#" -eq 0 ]; then
  # پشت reverse proxy (کانتینر frontend/Nginx)، IP واقعی کلاینت از X-Forwarded-For
  # می‌آید؛ بدون --proxy-headers محدودیت نرخ ورود برای کل سازمان یک سطل مشترک می‌شود.
  # FORWARDED_ALLOW_IPS باید به IP/شبکهٔ پروکسی محدود شود؛ با «*» بک‌اند هر
  # X-Forwarded-For ی را باور می‌کند. در ENVIRONMENT=production مقدار «*» عمداً
  # باعث خطای استارت‌آپ می‌شود (app/core/config.py).
  exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
    --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}"
else
  exec "$@"
fi
