"""P1-03 — زیرساخت تحویل بیرونی اعلان‌ها.

این قابلیت هنوز به هیچ سرویس واقعی وصل نیست، و همین نکته است: **زیرساخت باید
پیش از انتخاب ارائه‌دهنده کامل و آزموده باشد**، وگرنه انتخاب اول به وابستگی
دائمی تبدیل می‌شود.

پس این فایل چیزی را می‌سنجد که به ارائه‌دهنده ربط ندارد:

* بدون تنظیمات، هیچ چیز عوض نمی‌شود — سامانه دقیقاً مثل امروز کار می‌کند.
* هیچ ارسالی داخل تراکنش گردش‌کار انجام نمی‌شود.
* کاربری که نخواسته، پیام نمی‌گیرد.
* شکستِ دائمی از شکستِ گذرا جدا می‌ماند.
* نشانی گیرنده در لحظهٔ ثبت قفل می‌شود.
"""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.enums import DeliveryChannel, DeliveryStatus
from app.models.notification import Notification
from app.models.notification_delivery import NotificationDelivery
from app.services import channels
from app.services.channels.base import DeliveryError, Message
from app.services.delivery import OUTBOUND_TYPES, enqueue_for, run_delivery_sweep
from app.services.notifications import notify
from tests.helpers import make_user


class RecordingChannel:
    """کانال آزمایشی: هرچه فرستاده شود را نگه می‌دارد، یا شکست دلخواه می‌دهد."""

    def __init__(self, kind=DeliveryChannel.email, *, fail=None):
        self.kind = kind
        self.sent: list[Message] = []
        self._fail = fail

    @property
    def is_configured(self) -> bool:
        return True

    def send(self, message: Message) -> None:
        if self._fail is not None:
            raise self._fail
        self.sent.append(message)


@pytest.fixture()
def wired(monkeypatch):
    """یک کانال ایمیلِ آزمایشی را جای کانال‌های واقعی می‌نشاند."""

    def _wire(channel):
        monkeypatch.setattr(channels, "_all_channels", lambda: [channel])
        return channel

    return _wire


def _contactable(db_session, **overrides):
    user = make_user(db_session, "hr")
    user.email = overrides.get("email", "kaveh@example.com")
    user.phone = overrides.get("phone", "09120000000")
    user.notify_by_email = overrides.get("notify_by_email", True)
    user.notify_by_sms = overrides.get("notify_by_sms", False)
    db_session.commit()
    return user


def _notify(db_session, user, type_="workflow_hr_approve"):
    notify(db_session, [user.id], type_=type_, message="پروندهٔ EVL-0007 در انتظار شماست", link="/evaluations/7")
    db_session.flush()


def _deliveries(db_session, user_id=None):
    stmt = select(NotificationDelivery)
    return list(db_session.scalars(stmt))


# ── خاموش بودن، حالت پیش‌فرض ────────────────────────────────────────────────

def test_with_no_channel_configured_nothing_changes(db_session):
    """مهم‌ترین تضمین این تغییر: تا وقتی کسی چیزی تنظیم نکرده، سامانه دقیقاً
    همان چیزی است که بود."""
    assert channels.available() == [], "پیش‌فرض باید خاموش باشد"

    user = _contactable(db_session)
    _notify(db_session, user)

    assert db_session.scalars(select(Notification)).all(), "اعلان درون‌برنامه‌ای باید ساخته شود"
    assert _deliveries(db_session) == [], "ولی هیچ ردیف تحویلی نباید ساخته شود"


def test_a_sweep_with_no_channel_is_a_no_op(db_session):
    assert run_delivery_sweep(db_session) == {"sent": 0, "failed": 0, "abandoned": 0}


# ── چه چیزی صف می‌شود ───────────────────────────────────────────────────────

def test_an_actionable_notification_is_queued(db_session, wired):
    wired(RecordingChannel())
    user = _contactable(db_session)

    _notify(db_session, user, "workflow_hr_approve")

    rows = _deliveries(db_session)
    assert len(rows) == 1
    assert rows[0].channel is DeliveryChannel.email
    assert rows[0].status is DeliveryStatus.pending
    assert rows[0].attempts == 0


def test_an_informational_notification_is_not_queued(db_session, wired):
    """«پرونده در صف بررسی قرار گرفت» اطلاع است، نه درخواست اقدام.

    اگر هر رویدادی پیامک بدهد، کاربر بعد از یک هفته همه را نادیده می‌گیرد — و
    آن‌وقت مهم‌ترینشان هم دیده نمی‌شود.
    """
    wired(RecordingChannel())
    user = _contactable(db_session)

    _notify(db_session, user, "workflow_submit")

    assert _deliveries(db_session) == []
    assert "workflow_submit" not in OUTBOUND_TYPES


def test_nothing_is_sent_during_the_workflow_transaction(db_session, wired):
    """ارسال هرگز روی مسیر درخواست نیست.

    اگر بود، کندی یا خطای سرویس پیامک به شکست «تأیید پرونده» ترجمه می‌شد —
    همان اشتباهی که برای رندر PDF مرتکب شده بودیم و در P2-05 اصلاحش کردیم.
    """
    channel = wired(RecordingChannel())
    user = _contactable(db_session)

    _notify(db_session, user)

    assert channel.sent == [], "ثبت باید انجام شود، ارسال نه"


# ── ارجحیت کاربر ────────────────────────────────────────────────────────────

def test_a_user_who_opted_out_gets_nothing(db_session, wired):
    wired(RecordingChannel())
    user = _contactable(db_session, notify_by_email=False)

    _notify(db_session, user)

    assert _deliveries(db_session) == []


def test_a_user_with_no_address_gets_nothing(db_session, wired):
    """تیک زده ولی نشانی ندارد — نباید ردیفی ساخته شود که قرار نیست برسد."""
    wired(RecordingChannel())
    user = _contactable(db_session, email=None, notify_by_email=True)

    _notify(db_session, user)

    assert _deliveries(db_session) == []


def test_an_inactive_user_gets_nothing(db_session, wired):
    wired(RecordingChannel())
    user = _contactable(db_session)
    user.is_active = False
    db_session.commit()

    _notify(db_session, user)

    assert _deliveries(db_session) == []


def test_each_configured_channel_the_user_wants_gets_its_own_row(db_session, monkeypatch):
    monkeypatch.setattr(
        channels,
        "_all_channels",
        lambda: [RecordingChannel(DeliveryChannel.email), RecordingChannel(DeliveryChannel.sms)],
    )
    user = _contactable(db_session, notify_by_email=True, notify_by_sms=True)

    _notify(db_session, user)

    rows = _deliveries(db_session)
    assert {row.channel for row in rows} == {DeliveryChannel.email, DeliveryChannel.sms}


# ── ارسال ───────────────────────────────────────────────────────────────────

def test_the_sweep_sends_and_records_success(db_session, wired):
    channel = wired(RecordingChannel())
    user = _contactable(db_session)
    _notify(db_session, user)

    outcome = run_delivery_sweep(db_session)

    assert outcome["sent"] == 1
    assert len(channel.sent) == 1
    assert channel.sent[0].recipient == "kaveh@example.com"
    assert "EVL-0007" in channel.sent[0].body
    assert channel.sent[0].link == "/evaluations/7"

    row = _deliveries(db_session)[0]
    assert row.status is DeliveryStatus.sent
    assert row.sent_at is not None
    assert row.last_error is None


def test_a_sent_row_is_not_sent_again(db_session, wired):
    channel = wired(RecordingChannel())
    user = _contactable(db_session)
    _notify(db_session, user)

    run_delivery_sweep(db_session)
    run_delivery_sweep(db_session)

    assert len(channel.sent) == 1, "جارو هر پنج دقیقه اجرا می‌شود؛ نباید دوباره بفرستد"


# ── شکست ────────────────────────────────────────────────────────────────────

def test_a_permanent_failure_is_abandoned_immediately(db_session, wired):
    """شمارهٔ نامعتبر با تلاش دوباره درست نمی‌شود؛ تکرارش فقط سهمیه را می‌سوزاند."""
    wired(RecordingChannel(fail=DeliveryError("گیرنده نامعتبر است", retryable=False)))
    user = _contactable(db_session)
    _notify(db_session, user)

    outcome = run_delivery_sweep(db_session)

    row = _deliveries(db_session)[0]
    assert outcome["abandoned"] == 1
    assert row.status is DeliveryStatus.abandoned
    assert row.attempts == 1
    assert "نامعتبر" in row.last_error


def test_a_transient_failure_is_retried(db_session, wired):
    wired(RecordingChannel(fail=DeliveryError("شبکه قطع است", retryable=True)))
    user = _contactable(db_session)
    _notify(db_session, user)

    outcome = run_delivery_sweep(db_session)

    row = _deliveries(db_session)[0]
    assert outcome["failed"] == 1
    assert row.status is DeliveryStatus.failed, "باید دوباره تلاش شود، نه رها"
    assert row.attempts == 1


def test_retries_back_off_instead_of_hammering(db_session, wired):
    """سرویسی که موقتاً پایین است نباید هر پنج دقیقه همان بار را دوباره بگیرد."""
    wired(RecordingChannel(fail=DeliveryError("۵۰۳", retryable=True)))
    user = _contactable(db_session)
    _notify(db_session, user)

    run_delivery_sweep(db_session)
    immediately_after = run_delivery_sweep(db_session)

    assert immediately_after["failed"] == 0, "تلاش دوم نباید بلافاصله انجام شود"
    assert _deliveries(db_session)[0].attempts == 1


def test_a_transient_failure_is_eventually_abandoned(db_session, wired):
    """ردیفی که تا ابد تلاش کند، صف را برای بقیه می‌بندد."""
    wired(RecordingChannel(fail=DeliveryError("همیشه شکست", retryable=True)))
    user = _contactable(db_session)
    _notify(db_session, user)
    row = _deliveries(db_session)[0]

    for _ in range(settings.delivery_max_attempts):
        # عقب‌نشینی را عقب می‌کشیم تا لازم نباشد تست واقعاً منتظر بماند
        row.last_attempt_at = datetime.now(UTC) - timedelta(days=1)
        run_delivery_sweep(db_session)

    assert row.status is DeliveryStatus.abandoned
    assert row.attempts == settings.delivery_max_attempts


def test_an_unexpected_error_does_not_stop_the_sweep(db_session, monkeypatch):
    """یک کانال بدرفتار نباید بقیهٔ صف را بخواباند."""

    class Exploding(RecordingChannel):
        def send(self, message):
            raise RuntimeError("چیزی که پیش‌بینی نشده بود")

    monkeypatch.setattr(channels, "_all_channels", lambda: [Exploding()])
    user = _contactable(db_session)
    _notify(db_session, user)

    outcome = run_delivery_sweep(db_session)

    assert outcome["failed"] == 1
    assert "پیش‌بینی‌نشده" in _deliveries(db_session)[0].last_error


# ── عکس‌برداری از نشانی ─────────────────────────────────────────────────────

def test_the_recipient_is_frozen_at_enqueue_time(db_session, wired):
    """اگر کاربر فردا نشانی‌اش را عوض کند، تلاش مجددِ پیامِ دیروز نباید به نشانی
    تازه برود: آن پیام برای مخاطبِ آن روز بوده، و زنجیرهٔ حسابرسی باید بگوید به
    کجا فرستاده شد."""
    channel = wired(RecordingChannel(fail=DeliveryError("گذرا", retryable=True)))
    user = _contactable(db_session, email="old@example.com")
    _notify(db_session, user)
    run_delivery_sweep(db_session)

    user.email = "new@example.com"
    db_session.commit()
    row = _deliveries(db_session)[0]
    row.last_attempt_at = datetime.now(UTC) - timedelta(days=1)
    channel._fail = None
    run_delivery_sweep(db_session)

    assert channel.sent[0].recipient == "old@example.com"


# ── پیکربندی کانال ──────────────────────────────────────────────────────────

def test_an_unconfigured_smtp_channel_reports_itself_as_such():
    """کانالِ نیمه‌تنظیم‌شده هرگز نباید در صف بنشیند: پیام‌هایی می‌سازد که قرار
    نیست برسند و صف را با شکست‌های پیکربندی پر می‌کند."""
    from app.services.channels.smtp import SmtpChannel

    assert SmtpChannel().is_configured is False


def test_an_unconfigured_sms_channel_reports_itself_as_such():
    from app.services.channels.http_sms import HttpSmsChannel

    assert HttpSmsChannel().is_configured is False


def test_the_sms_template_escapes_the_message_for_its_context(monkeypatch):
    """متن اعلان‌های این سامانه فارسی است و گیومه و پرانتز دارد. بدون کدگذاریِ
    مناسبِ بافت، همان متن درخواست را می‌شکند."""
    from app.services.channels.http_sms import _render

    monkeypatch.setattr(settings, "sms_api_key", "KEY")

    url = _render(
        "https://x/{api_key}/send?to={recipient}&text={message}",
        recipient="09120000000",
        message="پرونده EVL-1 (نام) & متن",
        quote="url",
    )
    assert " " not in url.split("text=")[1]
    assert "&" not in url.split("text=")[1]

    body = _render(
        '{"text": "{message}"}',
        recipient="09120000000",
        message='او گفت "سلام"',
        quote="json",
    )
    import json

    assert json.loads(body)["text"] == 'او گفت "سلام"'
