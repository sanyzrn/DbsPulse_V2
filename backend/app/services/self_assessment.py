"""خودارزیابی: چه وقت باز است، و دعوت‌کردنِ کارمند به انجامش.

مسئله
-----
خودارزیابی از قبل وجود داشت و کار می‌کرد، ولی هیچ‌کس خبر نداشت. کارمند فقط اگر
خودش وارد سامانه می‌شد و پروندهٔ بازش را پیدا می‌کرد می‌فهمید که می‌تواند نظرش
را ثبت کند. «اختیاری» با «کسی خبرش نکرده» یکی نیست.

پس یک دعوتِ صریح اضافه شد: منابع انسانی از فهرست پرسنل دکمه را می‌زند، کارمند
اعلان داخلی می‌گیرد (و اگر ایمیل/پیامک تنظیم شده باشد، همان‌جا هم)، و دکمه تا
پایان همان پرونده غیرفعال می‌ماند.

چرا مسدودکننده نشد
------------------
وسوسه‌اش هست که خودارزیابی را پیش‌شرطِ شروعِ نمره‌دهی کنیم — «تا کارمند ثبت
نکند، مسئول واحد نتواند شروع کند». این کار نمی‌شود: یک کارمندِ در مرخصی یا
بی‌حوصله کلِ چرخهٔ ارزیابی سازمان را متوقف می‌کند، و همان بن‌بستی است که یک بار
از گردش‌کار حذف شد.

به‌جایش همان چیزی که در عمل جواب می‌دهد: پنجرهٔ خودارزیابی *پیش از* قطعی‌شدن
نمرهٔ ارزیاب باز است (`draft`، و در مسیر «مدیر» `hr_approved`)، دعوت زودتر
می‌رسد، و مسئول واحد پیش از ثبت می‌بیند که ثبت شده یا نه.
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import EvaluationStatus
from app.models.evaluation import EvaluationRecord
from app.models.personnel import Personnel
from app.models.user import User
from app.services.audit import log_event
from app.services.notifications import notify

#: خودارزیابی فقط تا پیش از قطعی‌شدن نمرهٔ ارزیاب معنا دارد: بعد از آن دیگر
#: «دیدگاه مستقل» نیست، واکنش به نمره است.
#:
#: مسیر عادی در `draft` (مسئول واحد هنوز نمره نداده)، مسیر «مدیر» در
#: `hr_approved` (معاونت خودش نمره‌دهندهٔ اول است و نمره‌اش هنوز قطعی نشده).
OPEN_STATUSES = frozenset({EvaluationStatus.draft, EvaluationStatus.hr_approved})

#: حالت‌هایی که رابط باید از هم جدا نشان بدهد. رشته و نه بولین: «دعوت نشده» و
#: «دعوت شده ولی انجام نداده» و «پرونده‌ای نیست» سه چیز متفاوت‌اند و هر سه به
#: کنشِ متفاوتی می‌رسند.
STATE_NO_CASE = "no_case"
STATE_NO_ACCOUNT = "no_account"
STATE_CLOSED = "closed"
STATE_PENDING = "pending"
STATE_INVITED = "invited"
STATE_SUBMITTED = "submitted"


def open_record_for(db: Session, personnel_id: int) -> EvaluationRecord | None:
    """پروندهٔ بازِ این فرد که هنوز پنجرهٔ خودارزیابی‌اش باز است."""
    return db.scalar(
        select(EvaluationRecord)
        .where(
            EvaluationRecord.subject_personnel_id == personnel_id,
            EvaluationRecord.status.in_(OPEN_STATUSES),
        )
        .order_by(EvaluationRecord.created_at.desc())
        .limit(1)
    )


def state_of(record: EvaluationRecord | None, has_account: bool) -> str:
    if record is None:
        return STATE_NO_CASE
    if record.self_assessment_submitted_at is not None:
        return STATE_SUBMITTED
    if record.status not in OPEN_STATUSES:
        return STATE_CLOSED
    if not has_account:
        return STATE_NO_ACCOUNT
    return STATE_INVITED if record.self_assessment_invited_at is not None else STATE_PENDING


def invite(db: Session, personnel: Personnel, actor_user_id: int) -> EvaluationRecord:
    """دعوت کارمند به خودارزیابی. خطاها همگی می‌گویند *چرا* و راهِ بعدی چیست."""
    account = db.scalar(select(User).where(User.personnel_id == personnel.id, User.is_active.is_(True)))
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "این فرد حساب کاربری فعالی ندارد، پس اعلانی دریافت نمی‌کند. "
                "ابتدا از همین صفحه برایش حساب بسازید."
            ),
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
    if record.self_assessment_invited_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="دعوت قبلاً برای این پرونده فرستاده شده است",
        )

    record.self_assessment_invited_at = datetime.now(UTC)
    record.self_assessment_invited_by_user_id = actor_user_id
    notify(
        db,
        [account.id],
        type_="self_assessment_invited",
        message=(
            "ارزیابی عملکرد شما آغاز شده است. پیش از آنکه نمرهٔ ارزیاب قطعی شود، "
            "می‌توانید دیدگاه خودتان را ثبت کنید."
        ),
        evaluation_record_id=record.id,
        link=f"/me?self-assessment={record.id}",
    )
    log_event(
        db,
        actor_user_id=actor_user_id,
        event_type="self_assessment_invited",
        evaluation_record_id=record.id,
        new_value={"personnel_id": personnel.id, "notified_user_id": account.id},
    )
    return record
