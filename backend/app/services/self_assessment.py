"""قواعد ارزیابی ۱۸۰ درجه: خودارزیابی مستقل در کنار ارزیابی مدیر.

هر دو فرم هم‌زمان باز می‌شوند و هرکدام پس از ثبت قفل می‌شود. خودارزیابی
اختیاری و غیرمسدودکننده است، مدیران آن را نمی‌بینند و جدول مقایسه تنها پس از
ثبت هر دو دیدگاه در اختیار منابع انسانی قرار می‌گیرد.
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
from app.services.evaluation_window import record_accepts_entries, require_record_window
from app.services.notifications import notify

OPEN_STATUSES = frozenset(
    {
        EvaluationStatus.draft,
        EvaluationStatus.submitted,
        EvaluationStatus.hr_approved,
        EvaluationStatus.deputy_approved,
    }
)

# مطابق سیاست این سازمان فقط مدیرعامل و معاونت‌ها مشمول نیستند.
ELIGIBLE_ROLES = frozenset(
    {UserRole.employee, UserRole.unit_supervisor, UserRole.hr, UserRole.support}
)

STATE_NO_CASE = "no_case"
STATE_NO_ACCOUNT = "no_account"
STATE_NOT_ELIGIBLE = "not_eligible"
STATE_CLOSED = "closed"
STATE_PENDING = "pending"
STATE_INVITED = "invited"
STATE_SUBMITTED = "submitted"


def may_view(record: EvaluationRecord, role: UserRole) -> bool:
    """مقایسه فقط برای HR و پس از قفل‌شدن ارزیابی مدیر قابل مشاهده است."""
    return (
        role == UserRole.hr
        and record.self_assessment_submitted_at is not None
        and record.status != EvaluationStatus.draft
    )


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
    if account_role not in ELIGIBLE_ROLES:
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
    if account.role not in ELIGIBLE_ROLES:
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
    require_record_window(db, record)

    _deliver_invitation(
        db,
        record=record,
        personnel=personnel,
        account=account,
        actor_user_id=actor_user_id,
        is_reminder=record.self_assessment_invited_at is not None,
    )
    return record
