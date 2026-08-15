"""کانال ایمیل روی SMTP (P1-03).

SMTP عمداً انتخاب شده و نه API یک سرویس خاص: پروتکل استاندارد است، پس همان کد
با Gmail، با میل‌سرور داخلی سازمان، و با هر سرویس تراکنشی کار می‌کند. وصل‌کردنش
فقط چند خط در `.env` است، بدون تغییر کد.
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings
from app.models.enums import DeliveryChannel
from app.services.channels.base import DeliveryError, Message

logger = logging.getLogger(__name__)

#: کدهای پاسخ SMTP که تلاش دوباره‌شان بی‌فایده است: گیرنده وجود ندارد، صندوق
#: بسته است، پیام رد شده. تلاش مجدد روی این‌ها فقط صف را مشغول می‌کند.
_PERMANENT_CODES = {550, 551, 553, 554}


class SmtpChannel:
    kind = DeliveryChannel.email

    @property
    def is_configured(self) -> bool:
        return bool(settings.smtp_host and settings.smtp_from)

    def send(self, message: Message) -> None:
        if not self.is_configured:
            raise DeliveryError("SMTP تنظیم نشده است", retryable=False)

        email = EmailMessage()
        email["From"] = settings.smtp_from
        email["To"] = message.recipient
        email["Subject"] = message.subject
        body = message.body
        if message.link:
            body = f"{body}\n\n{settings.public_base_url.rstrip('/')}{message.link}"
        email.set_content(body)

        try:
            if settings.smtp_use_ssl:
                server = smtplib.SMTP_SSL(
                    settings.smtp_host,
                    settings.smtp_port,
                    timeout=settings.smtp_timeout_seconds,
                    context=ssl.create_default_context(),
                )
            else:
                server = smtplib.SMTP(
                    settings.smtp_host,
                    settings.smtp_port,
                    timeout=settings.smtp_timeout_seconds,
                )
            with server:
                if settings.smtp_use_starttls and not settings.smtp_use_ssl:
                    server.starttls(context=ssl.create_default_context())
                if settings.smtp_username:
                    server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(email)
        except smtplib.SMTPResponseException as exc:
            raise DeliveryError(
                f"SMTP {exc.smtp_code}: {exc.smtp_error!r}",
                retryable=exc.smtp_code not in _PERMANENT_CODES,
            ) from exc
        except smtplib.SMTPRecipientsRefused as exc:
            raise DeliveryError(f"گیرنده پذیرفته نشد: {message.recipient}", retryable=False) from exc
        except (OSError, smtplib.SMTPException) as exc:
            # شبکه، DNS، مهلت — همگی گذرا هستند و ارزش تلاش دوباره دارند
            raise DeliveryError(f"اتصال SMTP ناموفق: {exc}", retryable=True) from exc
