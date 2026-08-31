"""خودارزیابی (ارزیابی ۱۸۰ درجه): چه کسی دارد، چه کسی می‌بیند، و دعوت به انجامش.

سه قاعده که منابع انسانی تعیین کرده و این ماژول تنها جای اعمالشان است.

۱. چه کسی خودارزیابی دارد — قاعده‌ای زنجیره‌محور، نه نقش‌محور
--------------------------------------------------------------
هر کسی که *موضوعِ* یک پروندهٔ ارزیابی است، مگر مدیرعامل و معاونت‌ها.

فهرستِ *منفی* است و نه مثبت، و این عمدی است: با فهرستِ مثبت، هر نقشِ تازه‌ای که
روزی اضافه شود بی‌صدا خودارزیابی‌اش را از دست می‌دهد و کسی خبردار نمی‌شود.

۲. چه کسی می‌بیند — فقط خودِ فرد و منابع انسانی
-----------------------------------------------
مدیر مستقیم، معاونت و مدیرعامل هیچ‌وقت. نه پیش از ثبتِ نمره‌شان، نه پس از آن.

پیش از این سه سوییچِ پنل مدیریت بود (پیش‌فرض خاموش) به‌علاوهٔ یک گاردِ زمانی.
هر دو برداشته شدند: به کارمند گفته می‌شود «فقط شما و منابع انسانی»، و سوییچی که
یک نفر می‌تواند بی‌سروصدا روشنش کند، آن جمله را به یک تنظیم تبدیل می‌کند نه یک
تضمین.

بهایش را می‌دانیم و پذیرفته‌ایم: گفت‌وگو دربارهٔ فاصلهٔ دو دیدگاه — که در ادبیاتِ
ارزیابیِ ۱۸۰ درجه فایدهٔ اصلی روش است — از مسیرِ مدیر مستقیم حذف می‌شود.

۳. پنجره: فقط `draft`، به‌علاوهٔ مهلتِ دوره
--------------------------------------------
خودارزیابی تا پیش از قطعی‌شدنِ نمرهٔ ارزیاب معنا دارد. بعد از آن دیگر «دیدگاهِ
مستقل» نیست، واکنش به نمره است — و کلِ ارزشِ جدولِ مقایسه به همین استقلال بند
است. مهلتِ تاریخیِ دوره یک شرطِ *دوم* است که به این اضافه می‌شود، نه جایگزینش
(`services/evaluation_window.py`).

دعوت، و اینکه چرا مسدودکننده نیست
---------------------------------
خودارزیابی از قبل کار می‌کرد ولی هیچ‌کس خبر نداشت؛ «اختیاری» با «کسی خبرش نکرده»
یکی نیست. پس منابع انسانی از فهرست پرسنل دعوت می‌فرستد و می‌تواند تکرارش کند.

مسدودکننده نشد چون یک کارمندِ در مرخصی کلِ چرخهٔ ارزیابی سازمان را متوقف می‌کرد
— همان بن‌بستی که یک بار از گردش‌کار حذف شد. به‌جایش مهلتِ واقعی گذاشته شد.

اعلانِ خودکار عمداً نیست
------------------------
هنگام باز شدنِ پرونده هیچ اعلانی نمی‌رود. تصمیمِ صریحِ منابع انسانی است: هیچ
پیامی نباید به فرد بگوید پرونده‌اش در حال بررسی است. تنها اعلان، همین دعوتِ
دستیِ خودارزیابی است و متنش هم فقط دربارهٔ خودِ خودارزیابی حرف می‌زند.
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import EvaluationStatus, UserRole
from app.models.evaluation import EvaluationRecord
from app.models.personnel import Personnel
from app.models.user import User
from app.services.audit import log_event
from app.services.evaluation_window import ensure_open as ensure_submission_window_open
from app.services.evaluation_window import record_accepts_entries
from app.services.notifications import notify

#: پنجرهٔ وضعیتیِ خودارزیابی — فقط `draft`.
#:
#: بازکردنش تا مرحله‌های بعد وسوسه‌انگیز است («چرا فرصت را کوتاه کنیم؟») ولی
#: استقلالِ دو دیدگاه را از بین می‌برد: پس از `submit` نمرهٔ ارزیاب قفل شده و هر
#: چیزی که فرد بعد از آن ثبت کند، دیگر دیدگاهِ مستقل نیست.
#:
#: `hr_approved` یک بار به‌اشتباه این‌جا بود و پنجره را ناپیوسته می‌کرد: باز در
#: `draft`، بسته در `submitted`، و دوباره باز در `hr_approved` — یعنی درست بعد
#: از آن‌که نمرهٔ ارزیاب ثبت *و* تأیید شده بود.
OPEN_STATUSES = frozenset({EvaluationStatus.draft})

#: نقش‌هایی که خودارزیابی ندارند — قاعدهٔ منابع انسانی: «همه، به‌جز مدیرعامل و
#: معاونت‌ها». فهرستِ منفی، تا نقشِ تازه بی‌صدا از قلم نیفتد.
EXCLUDED_ROLES = frozenset({UserRole.ceo, UserRole.deputy})

#: نقش‌هایی که خودارزیابیِ *دیگران* را می‌بینند. خودِ فرد از مسیرِ `/api/me` به
#: خودارزیابیِ خودش می‌رسد و این مجموعه دربارهٔ او حرف نمی‌زند.
VIEWER_ROLES = frozenset({UserRole.hr})


def may_self_assess(role: UserRole) -> bool:
    """آیا این نقش اصلاً خودارزیابی دارد؟

    شرطِ لازم است نه کافی: فرد باید موضوعِ همان پرونده هم باشد، که مسیرهای
    `/api/me` جداگانه می‌سنجند.
    """
    return role not in EXCLUDED_ROLES


#: حالت‌هایی که رابط باید از هم جدا نشان بدهد. رشته و نه بولین: «دعوت نشده» و
#: «دعوت شده ولی انجام نداده» و «پرونده‌ای نیست» سه چیز متفاوت‌اند و هر سه به
#: کنشِ متفاوتی می‌رسند.
STATE_NO_CASE = "no_case"
STATE_NO_ACCOUNT = "no_account"
STATE_NOT_ELIGIBLE = "not_eligible"
STATE_CLOSED = "closed"
STATE_PENDING = "pending"
STATE_INVITED = "invited"
STATE_SUBMITTED = "submitted"


def may_view(record: EvaluationRecord, role: UserRole) -> bool:
    """آیا این نقش می‌تواند خودارزیابیِ این پرونده را ببیند؟

    فقط منابع انسانی. نه مدیر مستقیم، نه معاونت، نه مدیرعامل — و نه پیش از ثبتِ
    نمره‌شان و نه پس از آن.

    شرطِ «فقط پس از خروج از `draft`» عمداً این‌جا نیست. منابع انسانی باید بتواند
    همان لحظه ببیند که خودارزیابی رسیده — وگرنه دعوت می‌فرستد و هیچ راهی ندارد
    بفهمد جواب گرفته یا نه. کاملِ *شدنِ جدولِ مقایسه* به ثبتِ هر دو طرف بند است،
    که خودِ جدول نشانش می‌دهد؛ آن یک چیزِ دیگر است.

    `record` در امضا مانده چون قاعده ممکن است دوباره پرونده‌محور شود؛ حذفش یعنی
    همهٔ فراخوان‌ها باید عوض شوند تا برگردد.
    """
    return role in VIEWER_ROLES


def open_record_for(db: Session, personnel_id: int) -> EvaluationRecord | None:
    """جدیدترین پرونده‌ای که هنوز امکان خودارزیابی برای آن وجود دارد."""
    return db.scalar(
        select(EvaluationRecord)
        .where(
            EvaluationRecord.subject_personnel_id == personnel_id,
            EvaluationRecord.status.in_(OPEN_STATUSES),
        )
        .order_by(EvaluationRecord.created_at.desc())
        .limit(1)
    )


def state_of(
    db: Session, record: EvaluationRecord | None, account_role: UserRole | None
) -> str:
    if record is None:
        return STATE_NO_CASE
    if account_role is None:
        return STATE_NO_ACCOUNT
    if not may_self_assess(account_role):
        return STATE_NOT_ELIGIBLE
    if record.self_assessment_submitted_at is not None:
        return STATE_SUBMITTED
    if record.status not in OPEN_STATUSES or not record_accepts_entries(db, record):
        return STATE_CLOSED
    return STATE_INVITED if record.self_assessment_invited_at is not None else STATE_PENDING


def _deliver_invitation(
    db: Session,
    *,
    record: EvaluationRecord,
    personnel: Personnel,
    account: User,
    actor_user_id: int,
    is_reminder: bool,
) -> None:
    record.self_assessment_invited_at = datetime.now(UTC)
    record.self_assessment_invited_by_user_id = actor_user_id
    notify(
        db,
        [account.id],
        type_="self_assessment_invited",
        message="یادآوری: لطفاً خودارزیابی این دوره را تا پایان مهلت ثبت کنید.",
        evaluation_record_id=record.id,
        link=f"/me?self-assessment={record.id}",
    )
    log_event(
        db,
        actor_user_id=actor_user_id,
        event_type="self_assessment_reminded" if is_reminder else "self_assessment_invited",
        evaluation_record_id=record.id,
        new_value={"personnel_id": personnel.id, "notified_user_id": account.id},
    )


def invite(db: Session, personnel: Personnel, actor_user_id: int) -> EvaluationRecord:
    """یادآوری دستی خودارزیابی؛ هیچ اعلان خودکاری برای موضوع پرونده نمی‌رود."""
    account = db.scalar(
        select(User).where(
            User.personnel_id == personnel.id,
            User.is_active.is_(True),
        )
    )
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "این فرد حساب کاربری فعالی ندارد، پس اعلانی دریافت نمی‌کند. "
                "ابتدا از همین صفحه برایش حساب بسازید."
            ),
        )
    if not may_self_assess(account.role):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="مدیرعامل و معاونت‌ها در این دوره مشمول خودارزیابی نیستند",
        )

    record = open_record_for(db, personnel.id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "پروندهٔ بازی برای این فرد وجود ندارد. خودارزیابی به یک پروندهٔ ارزیابی وصل "
                "می‌شود، پس ابتدا مسئول واحد باید پرونده را آغاز کند."
            ),
        )
    if record.self_assessment_submitted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این فرد خودارزیابی‌اش را قبلاً ثبت کرده است",
        )
    # دعوت‌کردن به کاری که مهلتش گذشته، فقط کاربر را سرِ دواندن است.
    ensure_submission_window_open(db, record, "خودارزیابی")

    _deliver_invitation(
        db,
        record=record,
        personnel=personnel,
        account=account,
        actor_user_id=actor_user_id,
        is_reminder=record.self_assessment_invited_at is not None,
    )
    return record
