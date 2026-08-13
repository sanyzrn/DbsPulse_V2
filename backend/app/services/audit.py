"""ثبت رویدادهای حسابرسی — با زنجیرهٔ هش، تا لاگ «مستندات» نباشد بلکه «مدرک» باشد.

مسئله (P1-09): لاگ فقط «به‌عرف» append-only بود. هیچ‌چیز جلوی UPDATE/DELETE روی
audit_log را نمی‌گرفت، پس این لاگ فقط برای کسی که *از قبل* به دارندهٔ دسترسی
دیتابیس اعتماد دارد چیزی را ثابت می‌کرد — و طبق P0-03 آن دسترسی دست همان نقشی
است که لاگ قرار بود پاسخ‌گو نگهش دارد.

راه‌حل، دو لایه:

* هر ردیف هشِ محتوای خودش را نگه می‌دارد، به‌علاوهٔ هشِ ردیف قبلی. دست‌بردن در یک
  ردیفِ میانی، همهٔ حلقه‌های بعدی را می‌شکند؛ بازنویسیِ نامرئی یعنی بازمحاسبهٔ کل
  دنبالهٔ بعد از آن.
* تریگر دیتابیس UPDATE و DELETE را روی جدول رد می‌کند (مایگریشن e8f4b127d905).
  تریگر به‌جای REVOKE استفاده شده چون این استقرار یک نقش دیتابیس بیشتر ندارد —
  همان نقشی که مایگریشن‌ها را هم اجرا می‌کند — پس REVOKE عملاً چیزی را نمی‌بست.

آن‌چه این‌جا *نیست*: ارسال به یک sink بیرونیِ append-only. زنجیرهٔ هش دست‌کاری را
قابل‌کشف می‌کند، ولی کسی که هم دیتابیس و هم کد را در اختیار دارد می‌تواند کل زنجیره
را از نو بسازد. کشفِ قطعی به یک نسخهٔ بیرون از کنترل همین برنامه نیاز دارد — یک
تصمیم زیرساختی که هنوز گرفته نشده است.
"""
import hashlib
import json

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

# ریشهٔ زنجیره: ردیف اول قبلی ندارد، پس به یک مقدار ثابت گره می‌خورد.
GENESIS_HASH = "0" * 64

# قفل توصیه‌ای مخصوص افزودن به زنجیره. بدون آن، دو تراکنش هم‌زمان می‌توانند یک
# prev_hash را بخوانند و زنجیره را دوشاخه کنند — که دقیقاً همان چیزی است که
# راستی‌آزمایی بعداً به‌عنوان «شکستگی» گزارش می‌کند.
_CHAIN_LOCK_KEY = 774_120_559


def _canonical(
    *,
    actor_user_id: int,
    event_type: str,
    evaluation_record_id: int | None,
    old_value: dict | None,
    new_value: dict | None,
    prev_hash: str,
) -> str:
    """نمایش متعارف محتوای یک ردیف.

    sort_keys برای این است که همان دادهٔ منطقی همیشه یک رشته بدهد — وگرنه ترتیب
    کلیدهای دیکشنری، هش را عوض می‌کرد و راستی‌آزمایی تصادفی شکست می‌خورد.
    created_at عمداً در هش نیست: مقدارش را سرور در لحظهٔ INSERT می‌گذارد و پیش از
    درج در دسترس نیست.
    """
    payload = {
        "actor_user_id": actor_user_id,
        "event_type": event_type,
        "evaluation_record_id": evaluation_record_id,
        "old_value": old_value,
        "new_value": new_value,
        "prev_hash": prev_hash,
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compute_hash(**fields) -> str:
    return hashlib.sha256(_canonical(**fields).encode("utf-8")).hexdigest()


def _last_hash(db: Session) -> str:
    last = db.scalar(select(AuditLog).order_by(AuditLog.id.desc()).limit(1))
    return last.entry_hash if last is not None else GENESIS_HASH


def log_event(
    db: Session,
    actor_user_id: int,
    event_type: str,
    evaluation_record_id: int | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
) -> None:
    # قفل تا پایان تراکنش نگه داشته می‌شود، پس افزودن‌های هم‌زمان سریالایز می‌شوند
    # و زنجیره دوشاخه نمی‌شود.
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _CHAIN_LOCK_KEY})

    prev_hash = _last_hash(db)
    entry_hash = compute_hash(
        actor_user_id=actor_user_id,
        event_type=event_type,
        evaluation_record_id=evaluation_record_id,
        old_value=old_value,
        new_value=new_value,
        prev_hash=prev_hash,
    )
    db.add(
        AuditLog(
            evaluation_record_id=evaluation_record_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            old_value=old_value,
            new_value=new_value,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )
    )
    db.flush()


def verify_chain(db: Session, limit: int | None = None) -> dict:
    """زنجیره را از ابتدا بازمحاسبه و با آن‌چه ذخیره شده مقایسه می‌کند.

    خروجی: وضعیت کلی + شناسهٔ اولین ردیفِ ناسازگار (اگر باشد). عمداً اولین را
    برمی‌گرداند نه همه: از نقطهٔ شکست به بعد همهٔ حلقه‌ها می‌شکنند، پس فهرست‌کردن
    همه‌شان فقط نویز است — چیزی که باید بررسی شود همان اولی است.
    """
    query = select(AuditLog).order_by(AuditLog.id)
    if limit is not None:
        query = query.limit(limit)

    checked = 0
    expected_prev = GENESIS_HASH
    for row in db.scalars(query):
        checked += 1
        recomputed = compute_hash(
            actor_user_id=row.actor_user_id,
            event_type=row.event_type,
            evaluation_record_id=row.evaluation_record_id,
            old_value=row.old_value,
            new_value=row.new_value,
            prev_hash=row.prev_hash,
        )
        if row.prev_hash != expected_prev:
            return {
                "ok": False,
                "checked": checked,
                "broken_at_id": row.id,
                "reason": "حلقهٔ زنجیره با ردیف قبلی نمی‌خواند (ردیفی حذف یا جابه‌جا شده)",
            }
        if recomputed != row.entry_hash:
            return {
                "ok": False,
                "checked": checked,
                "broken_at_id": row.id,
                "reason": "محتوای این ردیف با هشِ ثبت‌شده‌اش نمی‌خواند (ردیف ویرایش شده)",
            }
        expected_prev = row.entry_hash

    return {"ok": True, "checked": checked, "broken_at_id": None, "reason": None}
