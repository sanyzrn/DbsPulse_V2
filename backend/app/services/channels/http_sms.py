"""کانال پیامک، پیکربندی‌شونده از روی `.env` (P1-03).

**چرا پیکربندی به‌جای یک کلاس برای هر ارائه‌دهنده:** تقریباً همهٔ سرویس‌های پیامک
ایرانی یک درخواست HTTP ساده می‌گیرند — یک نشانی، یک کلید، شمارهٔ گیرنده و متن.
تفاوتشان در شکل درخواست است، نه در ماهیتش. پس به‌جای نوشتن یک کلاس برای هر
کدام (که یعنی هر ارائه‌دهندهٔ تازه = تغییر کد + استقرار)، خودِ شکل درخواست از
تنظیمات می‌آید.

نتیجه: وصل‌کردن یک سرویس تازه فقط چند خط در `.env` است.

```
# نمونه — سرویسی که با GET و پارامتر کار می‌کند
SMS_URL=https://api.example.com/v1/{api_key}/sms/send.json?receptor={recipient}&message={message}
SMS_METHOD=GET
SMS_API_KEY=xxxxx

# نمونه — سرویسی که JSON می‌خواهد
SMS_URL=https://api.example.com/v1/send/simple
SMS_METHOD=POST
SMS_HEADERS={"x-api-key": "{api_key}", "Content-Type": "application/json"}
SMS_BODY={"lineNumber": "3000x", "messageText": "{message}", "mobiles": ["{recipient}"]}
SMS_API_KEY=xxxxx
```

جای‌گزین‌ها `{recipient}`، `{message}` و `{api_key}` هستند. مقدارها پیش از
جای‌گذاری برای بافتِ خودشان (URL یا JSON) کدگذاری می‌شوند، وگرنه یک متن حاوی
گیومه یا `&` درخواست را خراب می‌کند.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from app.core.config import settings
from app.models.enums import DeliveryChannel
from app.services.channels.base import DeliveryError, Message

logger = logging.getLogger(__name__)

#: پاسخ‌هایی که تلاش دوباره‌شان بی‌فایده است: کلید غلط، دسترسی نداریم، شمارهٔ
#: نامعتبر. ۴۲۹ عمداً این‌جا نیست — سهمیهٔ تمام‌شده گذراست و باید دوباره تلاش شود.
_PERMANENT_STATUSES = {400, 401, 403, 404, 422}


def _render(template: str, *, recipient: str, message: str, quote: str) -> str:
    """جای‌گزین‌ها را با کدگذاریِ مناسبِ بافت می‌گذارد.

    `quote="url"` برای نشانی و `quote="json"` برای بدنهٔ JSON. بدون این، متنی که
    گیومه یا `&` دارد درخواست را می‌شکند — و متن اعلان‌های این سامانه فارسی است
    و «پرونده EVL-0007 (نام و نام خانوادگی)» دارد.
    """
    if quote == "url":
        escape = urllib.parse.quote
    else:
        # json.dumps یک رشتهٔ گیومه‌دار می‌دهد؛ گیومه‌های بیرونی را برمی‌داریم
        # چون قالب خودش آن‌ها را دارد.
        def escape(value: str) -> str:
            return json.dumps(value, ensure_ascii=False)[1:-1]

    return (
        template.replace("{recipient}", escape(recipient))
        .replace("{message}", escape(message))
        .replace("{api_key}", escape(settings.sms_api_key))
    )


class HttpSmsChannel:
    kind = DeliveryChannel.sms

    @property
    def is_configured(self) -> bool:
        return bool(settings.sms_url)

    def send(self, message: Message) -> None:
        if not self.is_configured:
            raise DeliveryError("سرویس پیامک تنظیم نشده است", retryable=False)

        text = message.body
        if message.link:
            text = f"{text}\n{settings.public_base_url.rstrip('/')}{message.link}"

        url = _render(settings.sms_url, recipient=message.recipient, message=text, quote="url")
        method = settings.sms_method.upper()

        data = None
        if settings.sms_body:
            body = _render(
                settings.sms_body, recipient=message.recipient, message=text, quote="json"
            )
            data = body.encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if settings.sms_headers:
            try:
                configured = json.loads(settings.sms_headers)
            except json.JSONDecodeError as exc:
                # پیکربندی غلط است، نه شبکه — تلاش دوباره درستش نمی‌کند.
                raise DeliveryError(f"SMS_HEADERS یک JSON معتبر نیست: {exc}", retryable=False) from exc
            headers.update(
                {
                    key: _render(str(value), recipient=message.recipient, message=text, quote="json")
                    for key, value in configured.items()
                }
            )

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=settings.sms_timeout_seconds) as response:
                payload = response.read(4096).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read(512).decode("utf-8", errors="replace")
            raise DeliveryError(
                f"HTTP {exc.code}: {detail[:200]}",
                retryable=exc.code not in _PERMANENT_STATUSES,
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise DeliveryError(f"اتصال به سرویس پیامک ناموفق: {exc}", retryable=True) from exc

        # برخی سرویس‌ها روی خطا هم ۲۰۰ می‌دهند و وضعیت را داخل بدنه می‌گذارند.
        # اگر الگوی موفقیت تنظیم شده باشد، بدنه هم بررسی می‌شود.
        if settings.sms_success_contains and settings.sms_success_contains not in payload:
            raise DeliveryError(f"پاسخ سرویس نشانهٔ موفقیت نداشت: {payload[:200]}", retryable=True)
