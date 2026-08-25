"""وضعیت پرونده‌های ارزیابی — چند پرونده کجاست، و چقدر آن‌جا مانده.

مسئله
-----
تا امروز فقط یک عدد در هر مرحله داشتیم: «چند پرونده الان این‌جاست». آن عدد
می‌گوید کجا شلوغ است، ولی نمی‌گوید **چرا**. صفِ ده‌تایی که هر پرونده‌اش نیم روز
می‌ماند، سالم است؛ صفِ دوتایی که هر کدام دو هفته مانده‌اند، نیست. با یک عدد،
هر دو یک شکل دیده می‌شوند.

پس این ماژول برای هر مرحله پنج چیز می‌دهد: چند پرونده تا حالا از این‌جا گذشته،
چند تا همین حالا این‌جاست، چند تا رد شده، چند درصد از کل، و میانگین توقف — و
همان‌ها را برای هر *شخصی* که مسئول آن مرحله بوده، جدا.

از کجا می‌آید
--------------
از خودِ لاگ ممیزی. هر گذار یک ردیف `status_changed` می‌سازد که می‌گوید پرونده از
چه وضعیتی به چه وضعیتی رفت و کِی. با کنار هم گذاشتنِ آن ردیف‌ها برای یک پرونده،
مدت‌زمانِ ماندنش در هر مرحله بیرون می‌آید.

جایگزینش این بود که برای هر مرحله یک ستون تاریخ به جدول پرونده‌ها اضافه کنیم —
که هم داده را دو جا می‌نوشت، هم برای پرونده‌هایی که *دو بار* از یک مرحله رد
شده‌اند (برگشت خورده‌اند) غلط بود: یک ستون فقط آخرین بار را نگه می‌دارد.

نکتهٔ برگشت
------------
پروندهٔ برگشت‌خورده دو بار در یک مرحله می‌نشیند. هر دو نشستن شمرده می‌شود، و
`passes` می‌گوید چند بار — یعنی مرحله‌ای که `passes`ش خیلی بیشتر از `total`
است، همان جایی است که کار مدام برمی‌گردد.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.enums import EvaluationStatus, UserRole
from app.models.evaluation import EvaluationRecord
from app.models.user import User

#: مرحله‌ها به ترتیبِ واقعیِ گردش‌کار، با «چه کسی الان نگهش داشته».
#:
#: «تأیید مدیرعامل» مرحلهٔ جدایی نیست: تأییدِ مدیرعامل همان رویدادی است که پرونده
#: را `finalized` می‌کند. یک ردیفِ جدا برایش، ردیفی می‌شد که همیشه صفر پروندهٔ
#: فعال دارد و تعداد بسته‌اش دقیقاً برابر «نهایی‌شده» است — یعنی یک تکرار.
STAGE_ORDER: tuple[EvaluationStatus, ...] = (
    EvaluationStatus.draft,
    EvaluationStatus.submitted,
    EvaluationStatus.hr_approved,
    EvaluationStatus.deputy_approved,
    EvaluationStatus.finalized,
)

#: «این مرحله روی میزِ چه کسی است» — نه اینکه چه کسی قبلاً کارش را کرده.
#: نامِ وضعیت از دیدِ گذشته نوشته شده («تأییدشده توسط HR») ولی آنچه مدیر لازم
#: دارد جهتِ رو به جلو است: این پرونده الان منتظرِ کیست.
STAGE_HOLDER: dict[EvaluationStatus, str] = {
    EvaluationStatus.draft: "مسئول واحد",
    EvaluationStatus.submitted: "منابع انسانی",
    EvaluationStatus.hr_approved: "معاونت",
    EvaluationStatus.deputy_approved: "مدیرعامل",
    EvaluationStatus.finalized: "—",
}

#: ستونی که می‌گوید در این مرحله پرونده دستِ چه کسی بوده.
#: `finalized` مسئول ندارد چون مرحله نیست، مقصد است.
_OWNER_FIELD: dict[EvaluationStatus, str | None] = {
    EvaluationStatus.draft: "unit_supervisor_user_id",
    EvaluationStatus.submitted: "hr_user_id",
    EvaluationStatus.hr_approved: "deputy_user_id",
    EvaluationStatus.deputy_approved: "ceo_user_id",
    EvaluationStatus.finalized: None,
}


@dataclass
class _Bucket:
    """جمع‌کنندهٔ خام؛ به عدد نهایی در `_finish` تبدیل می‌شود."""

    passes: int = 0
    active: int = 0
    closed: int = 0
    records: set[int] = field(default_factory=set)
    #: فقط ماندن‌های *تمام‌شده*. ماندنِ در جریان هنوز طول نهایی‌اش را ندارد و
    #: واردکردنش میانگین را به‌سمت پایین می‌کشد — دقیقاً برعکسِ چیزی که یک صفِ
    #: راکد باید نشان بدهد.
    finished_seconds: list[float] = field(default_factory=list)
    #: طولانی‌ترین ماندنِ در جریان: همان پرونده‌ای که باید سراغش رفت.
    longest_active_seconds: float = 0.0


def _stage_visits(
    created_at: datetime,
    current_status: str,
    stage_entered_at: datetime,
    transitions: list[tuple[datetime, str, str]],
    now: datetime,
) -> list[tuple[str, float, bool]]:
    """(وضعیت، ثانیهٔ ماندن، آیا هنوز همان‌جاست) برای یک پرونده.

    دو منبع، و هرکدام مرجعِ چیزی جداست:

    * **لاگ ممیزی** می‌گوید پرونده کِی از کجا به کجا رفت — یعنی مدت ماندن‌های
      *تمام‌شده*.
    * **خودِ ستون `status`** می‌گوید پرونده الان کجاست.

    منبع دوم لازم است چون لاگ ممکن است کامل نباشد: پرونده‌ای که مستقیم در
    دیتابیس ساخته شده (سیدِ دمو، مایگریشن، اصلاح دستی) هیچ ردیف `status_changed`
    ندارد. اگر فقط لاگ را می‌خواندیم، همهٔ آن پرونده‌ها «هنوز پیش‌نویس» شمرده
    می‌شدند — و ستونِ «فعال» عددی می‌داد که با خودِ فهرست پرونده‌ها نمی‌خواند.
    """
    visits: list[tuple[str, float, bool]] = []
    entered = created_at
    walking = EvaluationStatus.draft.value
    for at, from_status, _to_status in transitions:
        visits.append(((from_status or walking), (at - entered).total_seconds(), False))
        walking = _to_status
        entered = at
    # ماندنِ در جریان همیشه از خودِ پرونده می‌آید، نه از انتهای لاگ.
    visits.append((current_status, (now - stage_entered_at).total_seconds(), True))
    return visits


def stage_stats(db: Session) -> list[dict]:
    """آمار هر مرحله + تفکیک به‌ازای هر مسئول."""
    now = datetime.now(UTC)

    records = list(
        db.execute(
            select(
                EvaluationRecord.id,
                EvaluationRecord.created_at,
                EvaluationRecord.stage_entered_at,
                EvaluationRecord.status,
                EvaluationRecord.unit_supervisor_user_id,
                EvaluationRecord.hr_user_id,
                EvaluationRecord.deputy_user_id,
                EvaluationRecord.ceo_user_id,
            )
        ).all()
    )
    if not records:
        return [
            {
                "status": status.value,
                "holder": STAGE_HOLDER[status],
                "total": 0,
                "active": 0,
                "closed": 0,
                "passes": 0,
                "share_pct": 0.0,
                "avg_dwell_days": None,
                "longest_active_days": None,
                "by_owner": [],
            }
            for status in STAGE_ORDER
        ]

    owners_by_record = {
        row.id: {
            "unit_supervisor_user_id": row.unit_supervisor_user_id,
            "hr_user_id": row.hr_user_id,
            "deputy_user_id": row.deputy_user_id,
            "ceo_user_id": row.ceo_user_id,
        }
        for row in records
    }

    transitions: dict[int, list[tuple[datetime, str, str]]] = defaultdict(list)
    for row in db.execute(
        select(AuditLog.evaluation_record_id, AuditLog.created_at, AuditLog.old_value, AuditLog.new_value)
        .where(AuditLog.event_type == "status_changed", AuditLog.evaluation_record_id.is_not(None))
        .order_by(AuditLog.created_at)
    ).all():
        from_status = (row.old_value or {}).get("status", "")
        to_status = (row.new_value or {}).get("status", "")
        # ساختِ پرونده هم یک ردیف `status_changed` می‌سازد، ولی بدون `old_value`:
        # «از هیچ به پیش‌نویس». آن یک *تولد* است، نه گذار — و شمردنش یعنی هر
        # پرونده یک ماندنِ صفرثانیه‌ای در پیش‌نویس اضافه می‌کرد که هم تعداد را
        # دو برابر می‌کرد و هم میانگین توقف را به‌سمت صفر می‌کشید.
        if not from_status or not to_status:
            continue
        transitions[row.evaluation_record_id].append((row.created_at, from_status, to_status))

    buckets: dict[str, _Bucket] = {status.value: _Bucket() for status in STAGE_ORDER}
    per_owner: dict[tuple[str, int], _Bucket] = defaultdict(_Bucket)

    for row in records:
        for status_value, seconds, is_current in _stage_visits(
            row.created_at,
            row.status.value,
            row.stage_entered_at,
            transitions.get(row.id, []),
            now,
        ):
            bucket = buckets.get(status_value)
            if bucket is None:
                # وضعیتی که در فهرست مرحله‌ها نیست (`cancelled`). پروندهٔ لغوشده
                # مرحله نیست، پایان است — و در آمارِ «کجا گیر کرده» جایی ندارد.
                continue
            bucket.passes += 1
            bucket.records.add(row.id)
            if is_current:
                bucket.active += 1
                bucket.longest_active_seconds = max(bucket.longest_active_seconds, seconds)
            else:
                bucket.closed += 1
                bucket.finished_seconds.append(seconds)

            owner_field = _OWNER_FIELD[EvaluationStatus(status_value)]
            owner_id = owners_by_record[row.id][owner_field] if owner_field else None
            if owner_id is None:
                continue
            owner_bucket = per_owner[(status_value, owner_id)]
            owner_bucket.passes += 1
            owner_bucket.records.add(row.id)
            if is_current:
                owner_bucket.active += 1
                owner_bucket.longest_active_seconds = max(owner_bucket.longest_active_seconds, seconds)
            else:
                owner_bucket.closed += 1
                owner_bucket.finished_seconds.append(seconds)

    owner_ids = {owner_id for _, owner_id in per_owner}
    names = {
        row.id: (row.full_name or row.username)
        for row in db.execute(select(User.id, User.username, User.full_name).where(User.id.in_(owner_ids))).all()
    } if owner_ids else {}

    total_records = len(records)
    result = []
    for status in STAGE_ORDER:
        bucket = buckets[status.value]
        owners = [
            _finish_owner(names.get(owner_id, "—"), owner_bucket)
            for (owner_status, owner_id), owner_bucket in per_owner.items()
            if owner_status == status.value
        ]
        # پرمشغله‌ترین اول: کسی که بیشترین پروندهٔ فعال را دارد، همان کسی است که
        # نگاهِ مدیر باید اول رویش بیفتد.
        owners.sort(key=lambda o: (-o["active"], -o["total"]))
        terminal = status is EvaluationStatus.finalized
        result.append(
            {
                "status": status.value,
                "holder": STAGE_HOLDER[status],
                "total": len(bucket.records),
                "active": bucket.active,
                "closed": bucket.closed,
                "passes": bucket.passes,
                "share_pct": round(len(bucket.records) * 100 / total_records, 1),
                # «نهایی‌شده» مرحلهٔ انتظار نیست، مقصد است: «چقدر آن‌جا مانده»
                # برایش یعنی «چند وقت است که تمام شده»، که پرسشِ دیگری است.
                "avg_dwell_days": None if terminal else _avg_days(bucket.finished_seconds),
                "longest_active_days": (
                    None
                    if terminal or not bucket.active
                    else round(bucket.longest_active_seconds / 86400, 1)
                ),
                "by_owner": owners,
            }
        )
    return result


def _finish_owner(name: str, bucket: _Bucket) -> dict:
    return {
        "name": name,
        "total": len(bucket.records),
        "active": bucket.active,
        "closed": bucket.closed,
        "avg_dwell_days": _avg_days(bucket.finished_seconds),
        "longest_active_days": (
            round(bucket.longest_active_seconds / 86400, 1) if bucket.active else None
        ),
    }


def _avg_days(seconds: list[float]) -> float | None:
    """`None` و نه صفر وقتی هیچ ماندنِ تمام‌شده‌ای نیست.

    صفر یعنی «فوری رد شد»، که ادعای دیگری است. مرحله‌ای که هنوز هیچ پرونده‌ای از
    آن رد نشده، میانگین ندارد — و رابط باید بتواند این دو را از هم جدا نشان دهد.
    """
    if not seconds:
        return None
    return round(max(0.0, sum(seconds) / len(seconds)) / 86400, 1)


#: نقش‌هایی که در هر مرحله می‌نشینند — برای مستندسازی و تست.
STAGE_ROLE: dict[EvaluationStatus, UserRole | None] = {
    EvaluationStatus.draft: UserRole.unit_supervisor,
    EvaluationStatus.submitted: UserRole.hr,
    EvaluationStatus.hr_approved: UserRole.deputy,
    EvaluationStatus.deputy_approved: UserRole.ceo,
    EvaluationStatus.finalized: None,
}
