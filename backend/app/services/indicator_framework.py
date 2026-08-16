"""خواندن و جلو بردن نسخهٔ چارچوب شاخص‌ها (P1-05).

کل ماژول دور یک تابع می‌چرخد: `indicator_ids_for_record`. هر جا که سؤال «این
پرونده باید به چه شاخص‌هایی نمره بگیرد» پرسیده می‌شود، باید از این‌جا بپرسد و نه
از `Indicator.is_active` — وگرنه همان خرابی‌ای که این تغییر برای رفعش آمده
برمی‌گردد، فقط از یک مسیر دیگر.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import EvaluationStatus
from app.models.evaluation import EvaluationRecord, EvaluationScore
from app.models.indicator import Indicator
from app.models.indicator_framework import IndicatorFramework

#: وضعیت‌هایی که یعنی «پرونده هنوز در جریان است». پرونده‌های نهایی‌شده و لغوشده
#: از هر تغییر چارچوبی مصون‌اند چون دیگر چیزی در آن‌ها نوشته نمی‌شود.
OPEN_STATUSES = (
    EvaluationStatus.draft,
    EvaluationStatus.submitted,
    EvaluationStatus.hr_approved,
    EvaluationStatus.deputy_approved,
)


def active_member_ids(db: Session) -> list[int]:
    """شناسهٔ شاخص‌های فعال، مرتب — عضویتِ نسخهٔ بعدی اگر همین حالا ساخته شود."""
    return sorted(db.scalars(select(Indicator.id).where(Indicator.is_active.is_(True))))


def current_framework(db: Session) -> IndicatorFramework | None:
    return db.scalar(select(IndicatorFramework).order_by(IndicatorFramework.version.desc()).limit(1))


def bump(
    db: Session,
    *,
    actor_user_id: int | None,
    change_kind: str,
    change_note: str | None = None,
) -> IndicatorFramework:
    """نسخهٔ تازه‌ای از روی مجموعهٔ فعالِ همین لحظه می‌سازد.

    باید *بعد از* `db.flush()` تغییرِ خودِ شاخص‌ها صدا زده شود، وگرنه عضویتی که
    می‌بیند هنوز عضویت قبلی است. commit با فراخواننده است تا نسخه و لاگ ممیزی در
    یک تراکنش بنشینند.
    """
    latest = current_framework(db)
    framework = IndicatorFramework(
        version=(latest.version if latest else 0) + 1,
        member_ids=active_member_ids(db),
        change_kind=change_kind,
        change_note=change_note,
        created_by_user_id=actor_user_id,
    )
    db.add(framework)
    db.flush()
    return framework


def ensure_framework(db: Session) -> IndicatorFramework:
    """نسخهٔ جاری، و اگر هیچ نسخه‌ای نیست بسازش.

    مایگریشن نسخهٔ ۱ را می‌سازد، پس در عمل این مسیر فقط برای دیتابیسی است که
    شاخص‌هایش بعد از مایگریشن از صفر ساخته شده‌اند (نمونهٔ آزمایشی، seed تازه).
    ۵۰۰ دادن به‌خاطر نبودِ ردیفی که خودمان می‌توانیم بسازیم، خدمتی به کسی نیست.
    """
    framework = current_framework(db)
    if framework is None or framework.member_ids != active_member_ids(db):
        framework = bump(db, actor_user_id=None, change_kind="seed")
    return framework


def indicator_ids_for_record(db: Session, record: EvaluationRecord) -> set[int]:
    """شاخص‌هایی که *این پرونده* باید به آن‌ها نمره بدهد.

    نکتهٔ کل این ماژول همین است: از مهرِ روی پرونده می‌خواند، نه از `is_active`.
    پرونده‌ای که دیروز باز شده با سؤال‌های دیروز بسته می‌شود، حتی اگر امروز
    منابع انسانی سؤالی اضافه یا کم کرده باشد.
    """
    if record.indicator_framework_id is not None:
        framework = db.get(IndicatorFramework, record.indicator_framework_id)
        if framework is not None:
            return set(framework.member_ids)
    # پروندهٔ بی‌مهر: نباید پیش بیاید. برگشتن به رفتار قبلی بهتر از ۵۰۰ است.
    return set(active_member_ids(db))


def indicators_for_record(db: Session, record: EvaluationRecord) -> dict[int, Indicator]:
    """همان مجموعه، این بار با ردیف کاملِ شاخص — برای رندر فرم و محاسبه.

    شاخصی که بعداً غیرفعال شده همچنان این‌جا می‌آید: پرونده‌ای که زیر آن نسخه باز
    شده هنوز به آن نمره می‌دهد، و فرمی که سؤال را نشان ندهد ولی نمره‌اش را لازم
    داشته باشد، بن‌بست است.
    """
    ids = indicator_ids_for_record(db, record)
    if not ids:
        return {}
    rows = db.scalars(select(Indicator).where(Indicator.id.in_(ids)))
    return {i.id: i for i in rows}


def impact_of_membership_change(db: Session) -> dict:
    """چه چیزی تحت تأثیر قرار می‌گیرد اگر همین حالا عضویت عوض شود.

    منابع انسانی حق دارد این را *قبل از* کلیک بداند. تا امروز نمی‌دانست، و چون
    خرابی هم بی‌صدا بود، معمولاً اولین کسی که می‌فهمید ارزیابی بود که فردا
    «ثبت»‌اش کار نمی‌کرد.
    """
    scored_subquery = (
        select(EvaluationScore.evaluation_record_id)
        .where(EvaluationScore.evaluation_record_id == EvaluationRecord.id)
        .exists()
    )
    open_records = select(EvaluationRecord).where(EvaluationRecord.status.in_(OPEN_STATUSES))

    frozen = db.scalar(
        select(func.count()).select_from(open_records.where(scored_subquery).subquery())
    )
    movable = db.scalar(
        select(func.count()).select_from(open_records.where(~scored_subquery).subquery())
    )
    return {"frozen_open_records": frozen or 0, "movable_open_records": movable or 0}


def rebind_untouched_open_records(db: Session, framework: IndicatorFramework) -> int:
    """پرونده‌های بازی که هنوز هیچ امتیازی نخورده‌اند را به نسخهٔ تازه می‌برد.

    این کار بی‌خطر است *دقیقاً چون* امتیازی وجود ندارد که بشکند، و همان چیزی است
    که منابع انسانی انتظار دارد: پرونده‌ای که هیچ‌کس دستش نزده باید سؤال‌های
    امروز را بپرسد. پرونده‌ای که نیمه‌کاره پر شده دست نمی‌خورد — همان‌جاست که
    پایداری اهمیت دارد.
    """
    scored = (
        select(EvaluationScore.evaluation_record_id)
        .where(EvaluationScore.evaluation_record_id == EvaluationRecord.id)
        .exists()
    )
    untouched = db.scalars(
        select(EvaluationRecord).where(
            EvaluationRecord.status.in_(OPEN_STATUSES),
            EvaluationRecord.indicator_framework_id != framework.id,
            ~scored,
        )
    ).all()
    for record in untouched:
        record.indicator_framework_id = framework.id
    db.flush()
    return len(untouched)
