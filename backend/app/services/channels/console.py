"""کانال توسعه: به‌جای ارسال، در لاگ می‌نویسد (P1-03).

وجودش برای این است که کل مسیر — صف، تلاش مجدد، ارجحیت کاربر، جاروی تحویل —
بدون هیچ سرویس بیرونی و بدون هیچ هزینه‌ای قابل آزمودن باشد. بدون آن، تنها راهِ
دیدنِ این‌که زنجیره کار می‌کند، وصل‌کردن یک سرویس واقعی بود.
"""
import logging

from app.models.enums import DeliveryChannel
from app.services.channels.base import Message

logger = logging.getLogger("dbspulse.delivery")


class ConsoleChannel:
    def __init__(self, kind: DeliveryChannel) -> None:
        self.kind = kind

    @property
    def is_configured(self) -> bool:
        return True

    def send(self, message: Message) -> None:
        logger.info(
            "[%s] -> %s | %s | %s%s",
            self.kind.value,
            message.recipient,
            message.subject,
            message.body,
            f" ({message.link})" if message.link else "",
        )
