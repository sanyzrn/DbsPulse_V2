"""صف‌کردن و فرستادن اعلان‌های بیرونی (P1-03).

این ماژول تصمیم می‌گیرد *چه چیزی* بیرون برود و *کِی*؛ خودِ فرستادن کار کانال‌هاست.

**نه هر اعلانی بیرون می‌رود.** اعلان درون‌برنامه‌ای ارزان است — یک نقطهٔ قرمز روی
زنگوله. پیامک ارزان نیست، نه از نظر هزینه و نه از نظر توجه. اگر هر رویدادی
پیامک بدهد، کاربر بعد از یک هفته همه را نادیده می‌گیرد و ما دقیقاً همان چیزی را
از دست می‌دهیم که برای ساختنش این کار را کردیم.

پس فقط اعلان‌هایی بیرون می‌روند که **کسی باید کاری بکند** یا **نتیجه‌ای قطعی
شده**: نوبت تأیید، برگشت پرونده، یادآوری تأخیر، نهایی‌شدن. «پرونده در صف بررسی
قرار گرفت» بیرون نمی‌رود؛ آن اطلاع است، نه درخواست اقدام.
"""
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.text_limits import DELIVERY_ERROR_MAX
from app.models.enums import DeliveryChannel, DeliveryStatus
from app.models.notification import Notification
from app.models.notification_delivery import NotificationDelivery
from app.models.user import User
from app.services import channels
from app.services.channels import DeliveryError, Message

logger = logging.getLogger(__name__)

#: انواع اعلانی که ارزش قطع‌کردن روزِ کسی را دارند.
#:
#: معیار: یا کاری روی میز گیرنده است، یا چیزی دربارهٔ خودش قطعی شده. هر چیز
#: دیگری فقط در زنگوله می‌ماند.
OUTBOUND_TYPES: frozenset[str] = frozenset(
    {
        # نوبت اقدام رسیده
        "workflow_hr_approve",
        "workflow_deputy_approve",
        "workflow_reassigned",
        # پرونده برگشت خورده — یعنی کاری دوباره روی میز کسی است
        "workflow_hr_return",
        "workflow_deputy_return",
        "workflow_ceo_return",
        # نتیجهٔ قطعی دربارهٔ خودِ فرد
        "evaluation_finalized_self",
        # یادآوری‌های زمان‌بندی‌شده — کل دلیل وجودشان همین است که کسی وارد نشده
        "sla_reminder",
        "contract_expiry",
        "improvement_review_due",
        "orphaned_case",
        # ساخت دسته‌ای: ارزیاب باید بداند ده پرونده روی میزش آمده
        "bulk_evaluations_assigned",
    }
)


def _recipient_for(user: User, kind: DeliveryChannel) -> str | None:
    """نشانی گیرنده، اگر هم وجود داشته باشد و هم کاربر آن کانال را خواسته باشد."""
    if kind is DeliveryChannel.email:
        return user.email if user.notify_by_email and user.email else None
    return user.phone if user.notify_by_sms and user.phone else None


def enqueue_for(db: Session, notification: Notification) -> int:
    """ردیف‌های صندوق خروجی این اعلان را می‌سازد. خروجی: تعداد ردیف.

    هیچ چیزی فرستاده نمی‌شود — فقط ثبت. ارسال کار جاروست، بیرون از تراکنشِ
    گردش‌کار. اگر هیچ کانالی تنظیم نشده باشد، هیچ ردیفی ساخته نمی‌شود و رفتار
    سامانه دقیقاً همان چیزی می‌ماند که بود.
    """
    if notification.type not in OUTBOUND_TYPES:
        return 0

    configured = {channel.kind for channel in channels.available()}
    if not configured:
        return 0

    user = db.get(User, notification.user_id)
    if user is None or not user.is_active:
        return 0

    created = 0
    for kind in configured:
        recipient = _recipient_for(user, kind)
        if not recipient:
            continue
        db.add(
            NotificationDelivery(
                notification_id=notification.id,
                channel=kind,
                recipient=recipient,
                status=DeliveryStatus.pending,
            )
        )
        created += 1
    return created


def _subject_for(notification: Notification) -> str:
    """موضوع ایمیل. پیامک نادیده‌اش می‌گیرد."""
    return f"DbsPulse — {notification.message[:60]}"


def _retry_delay(attempts: int) -> timedelta:
    """فاصله تا تلاش بعدی، دو برابر در هر بار.

    بدون عقب‌نشینی، سرویسی که موقتاً پایین است هر پنج دقیقه همان بار را دوباره
    می‌گیرد و بازگشتش را سخت‌تر می‌کند.
    """
    return timedelta(minutes=settings.delivery_retry_base_minutes * (2 ** max(0, attempts - 1)))


def _is_due(delivery: NotificationDelivery, now: datetime) -> bool:
    if delivery.last_attempt_at is None:
        return True
    return delivery.last_attempt_at + _retry_delay(delivery.attempts) <= now


def run_delivery_sweep(db: Session, *, limit: int | None = None) -> dict[str, int]:
    """ردیف‌های در انتظار را می‌فرستد. نقطهٔ ورود جاروی زمان‌بند.

    commit با فراخواننده است، مثل بقیهٔ جاروها.
    """
    if not channels.available():
        return {"sent": 0, "failed": 0, "abandoned": 0}

    now = datetime.now(UTC)
    batch_size = limit or settings.delivery_batch_size
    # عقب‌نشینی نمایی در پایتون فیلتر می‌شود، نه در SQL: بیانش در SQL به ضرب
    # بازه در توان نیاز دارد و خوانایی‌اش را از دست می‌دهد. به‌جایش نامزدهای
    # بیشتری خوانده می‌شوند و آن‌هایی که هنوز نوبتشان نرسیده کنار می‌روند.
    candidates = db.scalars(
        select(NotificationDelivery)
        .where(
            NotificationDelivery.status.in_([DeliveryStatus.pending, DeliveryStatus.failed])
        )
        .order_by(NotificationDelivery.created_at)
        .limit(batch_size * 4)
    ).all()
    batch = [row for row in candidates if _is_due(row, now)][:batch_size]

    outcome = {"sent": 0, "failed": 0, "abandoned": 0}
    for delivery in batch:
        channel = channels.channel_for(delivery.channel)
        if channel is None:
            # کانالی که قبلاً تنظیم بوده و حالا نیست — ردیف دست‌نخورده می‌ماند
            # تا اگر دوباره تنظیم شد، برود.
            continue

        notification = db.get(Notification, delivery.notification_id)
        if notification is None:
            delivery.status = DeliveryStatus.abandoned
            delivery.last_error = "اعلان مرتبط دیگر وجود ندارد"
            outcome["abandoned"] += 1
            continue

        delivery.attempts += 1
        delivery.last_attempt_at = now
        try:
            channel.send(
                Message(
                    recipient=delivery.recipient,
                    subject=_subject_for(notification),
                    body=notification.message,
                    link=notification.link,
                )
            )
        except DeliveryError as exc:
            delivery.last_error = str(exc)[:DELIVERY_ERROR_MAX]
            # شکست دائمی همان‌جا رها می‌شود؛ تکرارش فقط سهمیه می‌سوزاند.
            # شکست گذرا تا سقف تلاش‌ها ادامه دارد و بعد رها می‌شود — یک ردیف که
            # تا ابد تلاش کند، صف را برای بقیه می‌بندد.
            if not exc.retryable or delivery.attempts >= settings.delivery_max_attempts:
                delivery.status = DeliveryStatus.abandoned
                outcome["abandoned"] += 1
                logger.warning(
                    "delivery %s abandoned after %s attempt(s): %s",
                    delivery.id,
                    delivery.attempts,
                    exc,
                )
            else:
                delivery.status = DeliveryStatus.failed
                outcome["failed"] += 1
        except Exception as exc:  # noqa: BLE001 — یک کانال بدرفتار نباید جارو را بخواباند
            delivery.status = DeliveryStatus.failed
            delivery.last_error = f"خطای پیش‌بینی‌نشده: {exc}"[:DELIVERY_ERROR_MAX]
            outcome["failed"] += 1
            logger.exception("delivery %s raised an unexpected error", delivery.id)
        else:
            delivery.status = DeliveryStatus.sent
            delivery.sent_at = datetime.now(UTC)
            delivery.last_error = None
            outcome["sent"] += 1

    return outcome
