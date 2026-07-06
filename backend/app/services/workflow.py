"""ماشین حالت گردش‌کار ارزیابی — به‌صورت اعلانی (declarative).

پیش از این هر endpoint گاردهای وضعیت/نقش/شخص را جداگانه و با کپی/پیست پیاده می‌کرد
(و ناهماهنگی هم داشت). حالا هر گذار مجاز یک ردیف داده است و یک تابع واحد اعتبارسنجی،
تغییر وضعیت و ثبت audit را انجام می‌دهد. ستون stage هم حذف شده و از status مشتق
می‌شود (schemas/evaluation.py) — دو ستونِ هم‌معنا دو منبع حقیقت بودند.
"""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import EvaluationStatus, UserRole
from app.models.evaluation import EvaluationRecord, EvaluationScore
from app.models.indicator import Indicator
from app.schemas.auth import CurrentUser
from app.services.audit import log_event
from app.services.evaluation import compute_result, validate_evidence


@dataclass(frozen=True)
class Transition:
    from_status: EvaluationStatus
    to_status: EvaluationStatus
    allowed_role: UserRole
    # نام فیلدی روی رکورد که شناسه کاربر مجاز را نگه می‌دارد؛ None یعنی هر کاربری با نقش مجاز
    assignee_field: str | None
    error_status: int
    error_detail: str


TRANSITIONS: dict[str, Transition] = {
    "submit": Transition(
        from_status=EvaluationStatus.draft,
        to_status=EvaluationStatus.submitted,
        allowed_role=UserRole.unit_supervisor,
        assignee_field="unit_supervisor_user_id",
        error_status=http_status.HTTP_403_FORBIDDEN,
        error_detail="این ارزیابی در مرحله ثبت توسط شما نیست",
    ),
    "hr_approve": Transition(
        from_status=EvaluationStatus.submitted,
        to_status=EvaluationStatus.hr_approved,
        allowed_role=UserRole.hr,
        assignee_field=None,
        error_status=http_status.HTTP_400_BAD_REQUEST,
        error_detail="این ارزیابی در انتظار بررسی منابع انسانی نیست",
    ),
    "deputy_approve": Transition(
        from_status=EvaluationStatus.hr_approved,
        to_status=EvaluationStatus.deputy_approved,
        allowed_role=UserRole.deputy,
        assignee_field="deputy_user_id",
        error_status=http_status.HTTP_403_FORBIDDEN,
        error_detail="این ارزیابی در مرحله تأیید معاونت توسط شما نیست",
    ),
    "ceo_finalize": Transition(
        from_status=EvaluationStatus.deputy_approved,
        to_status=EvaluationStatus.finalized,
        allowed_role=UserRole.ceo,
        assignee_field="ceo_user_id",
        error_status=http_status.HTTP_403_FORBIDDEN,
        error_detail="این ارزیابی در مرحله تأیید نهایی توسط شما نیست",
    ),
    # گذارهای «برگشت پرونده»: هر تأییدکننده می‌تواند پرونده را با ذکر دلیل یک مرحله
    # عقب بفرستد. امتیازهای قبلی حفظ می‌شوند تا نمره‌دهنده فقط موارد لازم را اصلاح کند.
    "hr_return": Transition(
        from_status=EvaluationStatus.submitted,
        to_status=EvaluationStatus.draft,
        allowed_role=UserRole.hr,
        assignee_field=None,
        error_status=http_status.HTTP_400_BAD_REQUEST,
        error_detail="این ارزیابی در انتظار بررسی منابع انسانی نیست",
    ),
    "deputy_return": Transition(
        from_status=EvaluationStatus.hr_approved,
        to_status=EvaluationStatus.submitted,
        allowed_role=UserRole.deputy,
        assignee_field="deputy_user_id",
        error_status=http_status.HTTP_403_FORBIDDEN,
        error_detail="این ارزیابی در مرحله بررسی معاونت توسط شما نیست",
    ),
    "ceo_return": Transition(
        from_status=EvaluationStatus.deputy_approved,
        to_status=EvaluationStatus.hr_approved,
        allowed_role=UserRole.ceo,
        assignee_field="ceo_user_id",
        error_status=http_status.HTTP_403_FORBIDDEN,
        error_detail="این ارزیابی در مرحله تأیید نهایی توسط شما نیست",
    ),
}


def ensure_transition_allowed(
    record: EvaluationRecord, action: str, current_user: CurrentUser
) -> Transition:
    spec = TRANSITIONS[action]
    denied = HTTPException(status_code=spec.error_status, detail=spec.error_detail)
    if record.status != spec.from_status or current_user.role != spec.allowed_role:
        raise denied
    if spec.assignee_field is not None and current_user.id != getattr(record, spec.assignee_field):
        raise denied
    return spec


def apply_transition(
    db: Session,
    record: EvaluationRecord,
    action: str,
    current_user: CurrentUser,
    before: Callable[[], None] | None = None,
) -> None:
    """اعتبارسنجی گذار، اجرای منطق اختصاصی (مثل نهایی‌سازی امتیازها)، تغییر وضعیت و audit."""
    spec = ensure_transition_allowed(record, action, current_user)
    if before is not None:
        before()
    old_status = record.status
    record.status = spec.to_status
    if spec.to_status == EvaluationStatus.finalized and record.finalized_at is None:
        record.finalized_at = datetime.now(UTC)
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="status_changed",
        evaluation_record_id=record.id,
        old_value={"status": old_status.value},
        new_value={"status": record.status.value},
    )
    # نفر بعدی زنجیره در همان تراکنش اعلان می‌گیرد (import محلی برای پرهیز از حلقه import)
    from app.services.notifications import notify_for_workflow_action

    notify_for_workflow_action(db, record, action)


def is_manager_path(record: EvaluationRecord) -> bool:
    """مسیر «مدیر»: مسئول واحد ندارد؛ معاونت خودش نمره‌دهنده اول است."""
    return record.unit_supervisor_user_id is None


def active_indicators_by_id(db: Session) -> dict[int, Indicator]:
    indicators = db.scalars(select(Indicator).where(Indicator.is_active.is_(True)))
    return {i.id: i for i in indicators}


def scores_as_dicts(db: Session, record: EvaluationRecord) -> list[dict]:
    scores = db.scalars(
        select(EvaluationScore).where(EvaluationScore.evaluation_record_id == record.id)
    )
    return [
        {"indicator_id": s.indicator_id, "score": s.score, "evidence_text": s.evidence_text}
        for s in scores
    ]


def finalize_scoring(db: Session, record: EvaluationRecord, current_user: CurrentUser) -> None:
    """اعتبارسنجی شواهد + کامل بودن شاخص‌ها + محاسبه درصدها؛ مشترک بین submit (مسئول واحد) و
    deputy-approve مسیر «مدیر» که در آن معاونت خودش نمره‌دهنده اول است."""
    indicators_by_id = active_indicators_by_id(db)
    scores = scores_as_dicts(db, record)

    scored_ids = {row["indicator_id"] for row in scores}
    if scored_ids != set(indicators_by_id.keys()):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="باید به تمام شاخص‌های فعال (عمومی و تخصصی) امتیاز داده شود",
        )

    try:
        validate_evidence(scores, indicators_by_id)
    except ValueError as exc:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    result = compute_result(scores, indicators_by_id)
    record.general_score_pct = result["general_score_pct"]
    record.specialized_score_pct = result["specialized_score_pct"]
    record.final_weighted_pct = result["final_weighted_pct"]
    record.recommendation = result["recommendation"]

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="score_submitted",
        evaluation_record_id=record.id,
        new_value=result,
    )
