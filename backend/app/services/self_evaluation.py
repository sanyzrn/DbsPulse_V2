"""تفکیک وظایف روی یک زنجیرهٔ ارزیابی — دو قاعده که هر دو یک چیز می‌گویند:
هیچ‌کس نباید دربارهٔ خودش تصمیم بگیرد، و هیچ‌کس نباید دو بار در یک تصمیم رأی
بدهد.

P0-10 — هیچ‌کس نباید ارزیابِ خودش باشد.

پیوند «کاربر ← پرسنل» از طریق `users.personnel_id` است، پس تداخل وقتی رخ می‌دهد که
یکی از سه ارزیابِ یک پرسنل، کاربری باشد که `personnel_id`اش همان پرسنل است. دو مسیر
می‌توانند این وضعیت را بسازند و هر دو گارد دارند:

1. HR دسترسی ارزیابی را تنظیم می‌کند و کاربرِ خودِ فرد را ارزیاب می‌گذارد.
2. دسترسی از قبل درست بوده و HR بعداً کاربرِ ارزیاب را به همان پرسنل لینک می‌کند.

این‌ها گاردهای *کد* برای پیام خطای تمیز هستند؛ پشتیبان واقعی، تریگرهای دیتابیس در
مایگریشن c3e8b1a76d94 است که مسیرهای دیگر (SQL دستی، endpoint آینده) را هم می‌گیرد.
"""
from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.evaluation import EvaluationRecord
from app.models.evaluation_access import EvaluationAccess
from app.models.user import User

_CONFLICT_DETAIL = (
    "یک نفر نمی‌تواند ارزیابِ خودش باشد؛ کاربر «{username}» به همین پرسنل متصل است."
)


def ensure_evaluators_are_not_the_subject(
    db: Session, personnel_id: int, evaluator_user_ids: list[int | None]
) -> None:
    """هنگام تنظیم دسترسی ارزیابی: هیچ‌یک از ارزیاب‌ها نباید خودِ این پرسنل باشد."""
    candidate_ids = [user_id for user_id in evaluator_user_ids if user_id is not None]
    if not candidate_ids:
        return

    conflicting = db.scalar(
        select(User.username).where(
            User.id.in_(candidate_ids), User.personnel_id == personnel_id
        )
    )
    if conflicting is not None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=_CONFLICT_DETAIL.format(username=conflicting),
        )


#: صندلی‌های تکراری‌ای که بیانِ درست‌تری دارند، و آن بیان چیست. کلید، جفتِ
#: مرتب‌شدهٔ نام فیلدهاست.
_REDUNDANT_PAIRS: dict[tuple[str, str], str] = {
    ("unit_supervisor_user_id", "deputy_user_id"): (
        "«مسئول واحد» و «معاونت» یک نفرند. اگر این فرد مستقیماً توسط معاونت ارزیابی "
        "می‌شود، «مسئول واحد» را خالی بگذارید؛ معاونت خودش نمره‌دهندهٔ اول می‌شود."
    ),
    ("deputy_user_id", "ceo_user_id"): (
        "«معاونت» و «مدیرعامل» یک نفرند. اگر این فرد معاونتی بالای سرش ندارد، "
        "«معاونت» را خالی بگذارید؛ پرونده از منابع انسانی مستقیم به مدیرعامل می‌رود."
    ),
}


def ensure_chain_stages_are_not_redundant(
    db: Session,
    unit_supervisor_user_id: int | None,
    deputy_user_id: int | None,
    ceo_user_id: int | None,
) -> None:
    """یک نفر نباید دو صندلیِ *قابل‌ادغام* را در یک زنجیره داشته باشد.

    ایراد درست است: `may_act_at` عمداً اجازه می‌دهد مافوق در مرحلهٔ پایین‌تر
    بنشیند (بدون آن، ساختار واقعی سازمان قابل ثبت نبود)، پس یک نفر می‌تواند دو
    صندلی بگیرد و لاگ ممیزی *دو تأیید* نشان بدهد — دو رویداد، دو مُهر، یک آدم.

    ولی «هر سه باید متفاوت باشند» پاسخ درستی نیست، چون یکی از سه ترکیب اصلاً
    تکراری نیست: کسی که مستقیماً زیر نظر مدیرعامل کار می‌کند. مدیرعامل هم
    نمره‌دهندهٔ اولش است و هم تأییدکنندهٔ نهایی، و بالای سرش کسِ دیگری *وجود
    ندارد*. ممنوع‌کردنش یعنی آن افراد قابل ثبت نیستند — همان اشتباهی که یک بار
    با NOT NULL بودنِ ستون معاونت مرتکب شدیم و آدم‌ها را وادار کرد معاونتِ
    ساختگی بنویسند.

    پس فقط صندلی‌هایی رد می‌شوند که *بیان دیگری* دارند؛ برای هرکدام هم پیام
    می‌گوید آن بیان چیست. حالتِ مجاز بی‌صدا نمی‌ماند: `single_decider` روی
    پرونده آن را علامت می‌زند و سند نهایی چاپش می‌کند
    (`app/services/snapshot.py`).
    """
    seats = {
        "unit_supervisor_user_id": unit_supervisor_user_id,
        "deputy_user_id": deputy_user_id,
        "ceo_user_id": ceo_user_id,
    }
    for (first, second), remedy in _REDUNDANT_PAIRS.items():
        if seats[first] is None or seats[second] is None:
            continue
        if seats[first] != seats[second]:
            continue
        username = db.scalar(select(User.username).where(User.id == seats[first]))
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"{remedy} (کاربر «{username}»)",
        )


def ensure_not_deciding_about_oneself(record, current_user) -> None:
    """کسی که موضوعِ پرونده است، نباید هیچ نقشی در رسیدگی به آن داشته باشد.

    سه مرحلهٔ زنجیره از قبل گارد داشتند، ولی مرحلهٔ منابع انسانی نه — و آن مرحله
    اتفاقاً تنها مرحله‌ای است که *صاحب از پیش تعیین‌شده* ندارد و از یک صف مشترک
    برداشته می‌شود. یعنی کارمندِ منابع انسانی می‌توانست پروندهٔ خودش را از صف
    بردارد، تأییدش کند، لغوش کند، یا اعتراض خودش را رد کند — و هیچ گاردی مانعش
    نبود، چون همهٔ آن endpointها فقط «نقش = hr» را می‌سنجیدند.

    گارد فقط روی *اقدام* نیست، روی *دیدن* هم هست: پیش از نهایی‌شدن، پروندهٔ در
    جریان شواهدِ ارزیاب را دارد. کسی که موضوع آن است نباید آن را از پنل HR بخواند.

    در سازمانی با یک نفر HR، این یعنی پروندهٔ خودِ او تا وقتی حساب HR دومی نباشد
    پیش نمی‌رود. این هزینه، آگاهانه است: بدیلش این است که یک نفر تنها، ارزیابیِ
    خودش را تأیید کند.
    """
    if current_user.personnel_id is None:
        return
    if current_user.personnel_id != record.subject_personnel_id:
        return
    raise HTTPException(
        status_code=http_status.HTTP_403_FORBIDDEN,
        detail=(
            "این پروندهٔ ارزیابیِ خودِ شماست؛ رسیدگی به آن باید توسط کاربر دیگری از "
            "منابع انسانی انجام شود."
        ),
    )


def ensure_user_link_is_not_self_evaluation(db: Session, user: User, personnel_id: int) -> None:
    """هنگام لینک کردن یک کاربر به پرسنل: آن کاربر نباید از قبل ارزیابِ همان پرسنل باشد."""
    is_evaluator_on_access = db.scalar(
        select(EvaluationAccess.id).where(
            EvaluationAccess.personnel_id == personnel_id,
            or_(
                EvaluationAccess.unit_supervisor_user_id == user.id,
                EvaluationAccess.deputy_user_id == user.id,
                EvaluationAccess.ceo_user_id == user.id,
            ),
        )
    )
    is_evaluator_on_record = db.scalar(
        select(EvaluationRecord.id).where(
            EvaluationRecord.subject_personnel_id == personnel_id,
            or_(
                EvaluationRecord.unit_supervisor_user_id == user.id,
                EvaluationRecord.deputy_user_id == user.id,
                EvaluationRecord.ceo_user_id == user.id,
            ),
        )
    )
    if is_evaluator_on_access is not None or is_evaluator_on_record is not None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=(
                f"کاربر «{user.username}» ارزیابِ این پرسنل است؛ نمی‌توان او را به "
                "همین پرسنل متصل کرد (کسی نمی‌تواند ارزیابِ خودش باشد)."
            ),
        )
