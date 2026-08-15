"""P0-10 — هیچ‌کس نباید ارزیابِ خودش باشد.

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
