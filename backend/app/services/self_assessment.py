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
نمرهٔ ارزیاب باز است (`draft`)، دعوت زودتر می‌رسد و در صورت لزوم تکرار می‌شود،
و مسئول واحد پیش از ثبت می‌بیند که ثبت شده یا نه.
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import EvaluationStatus, UserRole
from app.models.evaluation import EvaluationRecord
from app.models.personnel import Personnel
from app.models.user import User
from app.services.audit import log_event
from app.services.notifications import notify

#: خودارزیابی فقط تا پیش از قطعی‌شدن نمرهٔ ارزیاب معنا دارد: بعد از آن دیگر
#: «دیدگاه مستقل» نیست، واکنش به نمره است.
#:
#: فقط `draft` — هر دو مسیر (عادی و «مدیر») از همین وضعیت شروع می‌شوند.
#:
#: `hr_approved` یک بازماندهٔ قدیمی بود: زمانی مسیر «مدیر» مستقیماً در
#: `hr_approved` ساخته می‌شد. آن رفتار برداشته شد (توضیحش کنار ساختِ پرونده در
#: `api/routers/evaluations.py` است) ولی این عضو ماند و پنجره را ناپیوسته
#: می‌کرد: باز در `draft`، بسته در `submitted`، و دوباره باز در `hr_approved` —
#: یعنی درست بعد از آن‌که نمرهٔ ارزیاب ثبت *و* توسط منابع انسانی تأیید شده بود.
#: همان چیزی که سطر بالا می‌گوید نباید ممکن باشد.
OPEN_STATUSES = frozenset({EvaluationStatus.draft})

#: حالت‌هایی که رابط باید از هم جدا نشان بدهد. رشته و نه بولین: «دعوت نشده» و
#: «دعوت شده ولی انجام نداده» و «پرونده‌ای نیست» سه چیز متفاوت‌اند و هر سه به
#: کنشِ متفاوتی می‌رسند.
STATE_NO_CASE = "no_case"
STATE_NO_ACCOUNT = "no_account"
STATE_CLOSED = "closed"
STATE_PENDING = "pending"
STATE_INVITED = "invited"
STATE_SUBMITTED = "submitted"


#: نقش‌هایی که می‌توانند صندلیِ «نمره‌دهندهٔ اول» را داشته باشند.
#:
#: مدیرعامل در این فهرست نیست چون هیچ‌وقت نمره‌دهندهٔ اول نمی‌شود: مسیر عادی
#: وجودِ «مسئول واحد» را الزامی می‌کند و مسیر «مدیر» سازندهٔ پرونده را خودِ
#: معاونت می‌گذارد. منابع انسانی هم اصلاً نمره نمی‌دهد؛ کارش بررسی است.
_SCORING_ROLES = frozenset({UserRole.unit_supervisor, UserRole.deputy})


def policy_allows(role: UserRole) -> bool:
    """سیاستِ محرمانگیِ نقش‌محور — همان سوییچ‌های پنل مدیریت.

    این فقط می‌گوید «چه کسی مجاز است»، نه «چه وقت». برای تصمیمِ واقعیِ نمایش
    از `may_view` استفاده کنید؛ این تابع فقط جایی به‌کار می‌آید که خودِ پرونده
    در دست نیست — مثل تصمیم دربارهٔ فرستادن یا نفرستادنِ اعلان.
    """
    return {
        UserRole.hr: settings.self_assessment_visible_to_hr,
        UserRole.unit_supervisor: settings.self_assessment_visible_to_unit_supervisor,
        UserRole.deputy: settings.self_assessment_visible_to_deputy,
        UserRole.ceo: settings.self_assessment_visible_to_ceo,
    }.get(role, False)


def may_view(record: EvaluationRecord, role: UserRole) -> bool:
    """آیا این نقش می‌تواند خودارزیابیِ این پرونده را ببیند؟ دو شرط، نه یکی.

    سوییچِ نقش‌محور به‌تنهایی کافی نبود، و نبودنِ شرط دوم هدفِ خودِ قابلیت را
    خنثی می‌کرد.

    ارزشِ خودارزیابی در کنارِ هم دیدنِ دو دیدگاهِ *مستقل* است. ولی سوییچ فقط
    می‌گفت «چه کسی»، نه «چه وقت» — پس روشن‌کردنش برای مسئول واحد یعنی او نمرهٔ
    خودِ فرد را در وضعیت `draft` می‌دید، یعنی دقیقاً سرِ میزِ نمره‌دهی و پیش از
    ثبتِ نمرهٔ خودش. آن دیگر دیدگاهِ دوم نیست، لنگر است.

    و راهِ حلِ قبلی — خاموش‌گذاشتنِ سوییچ برای هر سه نقشِ تصمیم‌گیر — قابلیت را
    از کار می‌انداخت: خودارزیابی فقط به دستِ منابع انسانی می‌رسید، که نه نمره
    می‌دهد و نه در آن گفت‌وگو هست.

    پس گارد زمانی شد نه نقشی: تا وقتی پرونده در پنجرهٔ نمره‌دهی (`draft`) است،
    نمره‌دهنده آن را نمی‌بیند. پس از `submit` نمره‌اش قفل است و دیدنِ خودارزیابی
    دیگر لنگر نیست — همان‌جاست که گفت‌وگو دربارهٔ فاصله‌ها ممکن می‌شود.

    منابع انسانی و مدیرعامل از این گارد مستثنا هستند چون هیچ‌کدام نمره‌دهندهٔ
    اول نمی‌شوند (`_SCORING_ROLES`).
    """
    if not policy_allows(role):
        return False
    if role in _SCORING_ROLES and record.status in OPEN_STATUSES:
        return False
    return True


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
    # دعوتِ دوم «خطا» نیست، یادآوری است.
    #
    # پیش از این بارِ دوم ۴۰۹ می‌گرفت — برای همیشه. یعنی اگر اعلان گم می‌شد یا
    # کارمند آن را می‌بست، منابع انسانی هیچ راهی برای رساندنِ دوبارهٔ خبر نداشت
    # و تنها کارِ ممکن این بود که تلفنی بگوید. پنجره کوتاه است و فرصت از دست
    # می‌رفت. سرریزِ اعلان هم خطر نیست: هر یادآوری یک کلیکِ آگاهانهٔ منابع
    # انسانی است، نه چیزی خودکار.
    is_reminder = record.self_assessment_invited_at is not None

    record.self_assessment_invited_at = datetime.now(UTC)
    record.self_assessment_invited_by_user_id = actor_user_id
    notify(
        db,
        [account.id],
        type_="self_assessment_invited",
        message=(
            "یادآوری: هنوز خودارزیابیِ این دوره را ثبت نکرده‌اید. تا پیش از قطعی‌شدنِ "
            "نمرهٔ ارزیاب می‌توانید دیدگاهتان را ثبت کنید."
            if is_reminder
            else "ارزیابی عملکرد شما آغاز شده است. پیش از آنکه نمرهٔ ارزیاب قطعی شود، "
            "می‌توانید دیدگاه خودتان را ثبت کنید."
        ),
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
    return record
