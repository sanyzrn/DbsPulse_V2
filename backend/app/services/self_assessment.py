"""Contract-owned employee self-assessment rules.

Self-assessment is independent from an evaluation case. An eligible employee
may submit it once while their current employment contract is active. Keeping
the contract start date in the unique key means extending the same contract does
not reopen the form, while a genuinely new contract does.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contract_self_assessment import ContractSelfAssessment
from app.models.enums import PersonnelStatus, UserRole
from app.models.evaluation import EvaluationRecord
from app.models.indicator_framework import IndicatorFramework
from app.models.personnel import Personnel
from app.models.user import User
from app.services.audit import log_event
from app.services.indicator_framework import ensure_framework
from app.services.notifications import notify

EXCLUDED_ROLES = frozenset({UserRole.ceo, UserRole.deputy})
VIEWER_ROLES = frozenset({UserRole.hr})

# Kept for API compatibility with clients that know the old state vocabulary.
STATE_NO_CASE = "no_case"
STATE_NO_ACCOUNT = "no_account"
STATE_NOT_ELIGIBLE = "not_eligible"
STATE_CLOSED = "closed"
STATE_PENDING = "pending"
STATE_INVITED = "invited"
STATE_SUBMITTED = "submitted"


def may_self_assess(role: UserRole) -> bool:
    return role not in EXCLUDED_ROLES


def may_view(record: EvaluationRecord, role: UserRole) -> bool:
    """Only HR may view another employee's self-assessment."""
    return role in VIEWER_ROLES


def contract_is_open(personnel: Personnel, *, on: date | None = None) -> bool:
    today = on or date.today()
    return (
        personnel.status == PersonnelStatus.active
        and personnel.contract_start_date <= today <= personnel.contract_end_date
        and (personnel.separation_date is None or today < personnel.separation_date)
    )


def assessment_for_contract(db: Session, personnel_id: int, contract_start_date: date) -> ContractSelfAssessment | None:
    return db.scalar(
        select(ContractSelfAssessment).where(
            ContractSelfAssessment.personnel_id == personnel_id,
            ContractSelfAssessment.contract_start_date == contract_start_date,
        )
    )


def assessment_for_evaluation(db: Session, record: EvaluationRecord) -> ContractSelfAssessment | None:
    """Find the subject's submitted self-assessment for this case's contract."""
    contract_start = record.subject_contract_start_date
    if contract_start is None and record.subject is not None:
        contract_start = record.subject.contract_start_date
    if contract_start is None:
        return None
    assessment = assessment_for_contract(db, record.subject_personnel_id, contract_start)
    if assessment is None or assessment.submitted_at is None:
        return None
    return assessment


def indicator_ids_for_assessment(db: Session, assessment: ContractSelfAssessment) -> set[int]:
    framework = db.get(IndicatorFramework, assessment.indicator_framework_id)
    return set(framework.member_ids) if framework is not None else set()


def state_of(db: Session, personnel: Personnel, account_role: UserRole | None) -> str:
    if account_role is None:
        return STATE_NO_ACCOUNT
    if not may_self_assess(account_role):
        return STATE_NOT_ELIGIBLE

    assessment = assessment_for_contract(db, personnel.id, personnel.contract_start_date)
    # A submitted form remains visible after the contract ends.
    if assessment is not None and assessment.submitted_at is not None:
        return STATE_SUBMITTED
    if not contract_is_open(personnel):
        return STATE_CLOSED
    return STATE_INVITED if assessment is not None and assessment.invited_at else STATE_PENDING


def invite(db: Session, personnel: Personnel, actor_user_id: int) -> ContractSelfAssessment:
    """Send or repeat a reminder without creating an evaluation case."""
    account = db.scalar(
        select(User).where(
            User.personnel_id == personnel.id,
            User.is_active.is_(True),
        )
    )
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این فرد حساب کاربری فعال ندارد؛ ابتدا برای او حساب بسازید",
        )
    if not may_self_assess(account.role):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="مدیرعامل و معاونت‌ها مشمول خودارزیابی نیستند",
        )
    if not contract_is_open(personnel):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="قرارداد این فرد در حال حاضر فعال نیست",
        )

    assessment = assessment_for_contract(db, personnel.id, personnel.contract_start_date)
    if assessment is not None and assessment.submitted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این فرد خودارزیابی این قرارداد را قبلاً ثبت کرده است",
        )

    is_reminder = assessment is not None and assessment.invited_at is not None
    now = datetime.now(UTC)
    if assessment is None:
        framework = ensure_framework(db)
        assessment = ContractSelfAssessment(
            personnel_id=personnel.id,
            contract_start_date=personnel.contract_start_date,
            contract_end_date=personnel.contract_end_date,
            indicator_framework_id=framework.id,
        )
        db.add(assessment)
    else:
        # Extending the same contract must not create a second opportunity.
        assessment.contract_end_date = personnel.contract_end_date
    assessment.invited_at = now
    assessment.invited_by_user_id = actor_user_id
    db.flush()

    notify(
        db,
        [account.id],
        type_="self_assessment_invited",
        message="یادآوری: لطفاً خودارزیابی قرارداد جاری خود را ثبت کنید.",
        link="/me",
    )
    log_event(
        db,
        actor_user_id=actor_user_id,
        event_type="self_assessment_reminded" if is_reminder else "self_assessment_invited",
        new_value={
            "personnel_id": personnel.id,
            "contract_self_assessment_id": assessment.id,
            "contract_start_date": personnel.contract_start_date.isoformat(),
            "notified_user_id": account.id,
        },
    )
    return assessment
