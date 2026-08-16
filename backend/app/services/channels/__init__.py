"""کانال‌های تحویل بیرونی (P1-03).

`available()` تنها جایی است که بقیهٔ کد کانال‌ها را از آن می‌گیرد. اگر هیچ
کانالی تنظیم نشده باشد فهرست خالی برمی‌گردد و سامانه دقیقاً مثل قبل کار می‌کند:
اعلان درون‌برنامه‌ای ساخته می‌شود و هیچ چیز بیرون نمی‌رود.

**خاموش بودن، حالت پیش‌فرض است و باید بماند.** اولین باری که یک کانال روشن شود،
کل سازمان پیام می‌گیرد؛ این باید یک تصمیم آگاهانه باشد، نه اثر جانبی یک استقرار.
"""
from app.core.config import settings
from app.models.enums import DeliveryChannel
from app.services.channels.base import Channel, DeliveryError, Message
from app.services.channels.console import ConsoleChannel
from app.services.channels.http_sms import HttpSmsChannel
from app.services.channels.smtp import SmtpChannel

__all__ = [
    "Channel",
    "DeliveryError",
    "Message",
    "available",
    "channel_for",
]


def _all_channels() -> list[Channel]:
    if settings.notification_channel_console:
        # حالت توسعه: به‌جای ارسال واقعی، در لاگ می‌نویسد. جای هر دو کانال را
        # می‌گیرد تا بشود کل مسیر را بدون هیچ سرویس بیرونی آزمود.
        return [ConsoleChannel(DeliveryChannel.email), ConsoleChannel(DeliveryChannel.sms)]
    return [SmtpChannel(), HttpSmsChannel()]


def available() -> list[Channel]:
    """کانال‌هایی که واقعاً می‌شود با آن‌ها فرستاد."""
    return [channel for channel in _all_channels() if channel.is_configured]


def channel_for(kind: DeliveryChannel) -> Channel | None:
    for channel in available():
        if channel.kind is kind:
            return channel
    return None
