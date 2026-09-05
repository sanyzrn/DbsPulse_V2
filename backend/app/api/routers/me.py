"""«کارنامه من»: نمای شخصی کارمند از نتایج نهایی ارزیابی خودش + رؤیت رسمی.

کارمند (نقش employee) به پرونده کامل دسترسی ندارد — شواهد و کامنت‌های داخلی
زنجیره تأیید خصوصی می‌مانند؛ فقط خلاصه نتیجه نهایی‌شده را می‌بیند و با «رؤیت شد»
به‌صورت رسمی و قابل‌استناد (audit) تأیید می‌کند که نتیجه به او ابلاغ شده است.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_module, require_own_personnel
from app.core.config import settings
from app.db.session import get_db
from app.models.contract_self_assessment import (
    ContractSelfAssessment,
    ContractSelfAssessmentScore,
)
from app.models.enums import EvaluationStatus, ImprovementPlanStatus, UserRole
from app.models.evaluation import EvaluationRecord
from app.models.evaluation_period import EvaluationPeriod
from app.models.improvement_plan import ImprovementPlan
from app.models.personnel import Personnel
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.schemas.evaluation import (
    CurrentSelfAssessmentRead,
    MyEvaluationPage,
    MyEvaluationRead,
    MyOpenEvaluation,
    MySelfAssessmentRead,
    ObjectionRequest,
    SelfAssessmentRead,
    SelfAssessmentScoreRead,
    SelfAssessmentSubmit,
)
from app.schemas.improvement_plan import ImprovementPlanDetail
from app.services.audit import log_event
from app.services.evaluation_window import window_for
from app.services.indicator_framework import ensure_framework, indicator_ids_for_record
from app.services.notifications import notify
from app.services.self_assessment import (
    assessment_for_contract,
    contract_is_open,
    indicator_ids_for_assessment,
    may_self_assess,
)
from app.services.self_assessment import (
    state_of as self_assessment_state,
)
from app.services.workflow import IS_OPEN_RECORD

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("/evaluations", response_model=MyEvaluationPage)
def my_evaluations(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_own_personnel),
) -> MyEvaluationPage:
    if current_user.personnel_id is None:
        return MyEvaluationPage(total=0, items=[])
    query = select(EvaluationRecord).where(
        EvaluationRecord.subject_personnel_id == current_user.personnel_id,
        EvaluationRecord.status == EvaluationStatus.finalized,
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.order_by(EvaluationRecord.finalized_at.desc())))
    return MyEvaluationPage(total=total, items=[MyEvaluationRead.model_validate(r) for r in items])


@router.get("/evaluations/open", response_model=list[MyOpenEvaluation])
def my_open_evaluation(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_own_personnel),
) -> list[MyOpenEvaluation]:
    """پروندهٔ در جریانِ خود کارمند — فقط وضعیت، بدون هیچ امتیاز یا کامنتی.

    تا پیش از این کارمند هیچ نشانه‌ای نداشت که پرونده‌ای دربارهٔ او باز است؛ فرایند
    از دید او یک جعبهٔ سیاه بود که یک روز نتیجه‌اش اعلام می‌شد. دانستن «پرونده‌ای
    هست و الان روی میز چه کسی است» چیزی است که فرد حق دارد بداند، و هیچ ربطی به
    دیدن نمرهٔ پیش‌نویس ندارد — آن هنوز تصمیم نیست.
    """
    if current_user.personnel_id is None:
        return []
    records = db.scalars(
        select(EvaluationRecord)
        .where(
            EvaluationRecord.subject_personnel_id == current_user.personnel_id,
            IS_OPEN_RECORD,
        )
        .order_by(EvaluationRecord.created_at.desc())
    )
    result = []
    for record in records:
        period = db.get(EvaluationPeriod, record.period_id) if record.period_id else None
        window = window_for(db, record)
        result.append(
            MyOpenEvaluation.model_validate(record).model_copy(
                update={
                    "indicator_ids": sorted(indicator_ids_for_record(db, record)),
                    # سه شرط، و هر سه لازم: نقش خودارزیابی داشته باشد، پرونده
                    # هنوز در مرحلهٔ ثبت باشد، و مهلت نگذشته باشد. فرانت نباید
                    # هیچ‌کدام را خودش حساب کند.
                    # Self-assessment is contract-owned and rendered separately.
                    "self_assessment_open": False,
                    "period_name": period.name if period else None,
                    "period_ends_on": period.ends_on if period else None,
                    # مهلتِ واقعی — که ممکن است از تمدیدِ همین پرونده آمده باشد و
                    # با `period_ends_on` یکی نباشد.
                    "submission_deadline": window.closes_on,
                    "submission_deadline_extended": window.extended,
                }
            )
        )
    return result


@router.get("/self-assessments", response_model=list[MySelfAssessmentRead])
def my_self_assessments(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_own_personnel),
) -> list[MySelfAssessmentRead]:
    """تمام خودارزیابی‌های ثبت‌شدهٔ فرد، به تفکیک قرارداد."""
    if current_user.personnel_id is None:
        return []
    assessments = db.scalars(
        select(ContractSelfAssessment)
        .where(
            ContractSelfAssessment.personnel_id == current_user.personnel_id,
            ContractSelfAssessment.submitted_at.is_not(None),
        )
        .order_by(ContractSelfAssessment.submitted_at.desc())
    )
    return [
        MySelfAssessmentRead(
            assessment_id=assessment.id,
            personnel_id=assessment.personnel_id,
            contract_start_date=assessment.contract_start_date,
            contract_end_date=assessment.contract_end_date,
            submitted_at=assessment.submitted_at,
            note=assessment.note,
            scores=[SelfAssessmentScoreRead.model_validate(row) for row in assessment.scores],
        )
        for assessment in assessments
    ]


@router.get("/improvement-plans", response_model=list[ImprovementPlanDetail])
def my_improvement_plans(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_own_personnel),
) -> list[ImprovementPlan]:
    """برنامه‌های بهبودِ بازِ خود کارمند (فقط خواندنی) — تا بداند چه انتظاری از او می‌رود."""
    if current_user.personnel_id is None:
        return []
    return list(
        db.scalars(
            select(ImprovementPlan)
            .where(
                ImprovementPlan.personnel_id == current_user.personnel_id,
                ImprovementPlan.status == ImprovementPlanStatus.open,
            )
            .order_by(ImprovementPlan.review_date)
        )
    )


def _assessment_read(
    db: Session,
    personnel: Personnel,
    role: UserRole,
    assessment: ContractSelfAssessment | None = None,
) -> CurrentSelfAssessmentRead:
    assessment = assessment or assessment_for_contract(db, personnel.id, personnel.contract_start_date)
    eligible = may_self_assess(role)
    is_open = eligible and contract_is_open(personnel) and (assessment is None or assessment.submitted_at is None)
    indicator_ids: list[int] = []
    if assessment is not None:
        indicator_ids = sorted(indicator_ids_for_assessment(db, assessment))
    return CurrentSelfAssessmentRead(
        assessment_id=assessment.id if assessment else None,
        personnel_id=personnel.id,
        personnel_name=personnel.full_name,
        contract_start_date=personnel.contract_start_date,
        contract_end_date=personnel.contract_end_date,
        state=self_assessment_state(db, personnel, role),
        eligible=eligible,
        open=is_open,
        indicator_ids=indicator_ids,
        submitted_at=assessment.submitted_at if assessment else None,
        note=assessment.note if assessment else None,
        scores=[SelfAssessmentScoreRead.model_validate(row) for row in (assessment.scores if assessment else [])],
    )


def _ensure_current_assessment(
    db: Session,
    personnel: Personnel,
    role: UserRole,
    preferred_framework_id: int | None = None,
) -> ContractSelfAssessment | None:
    assessment = assessment_for_contract(db, personnel.id, personnel.contract_start_date)
    if assessment is not None or not may_self_assess(role) or not contract_is_open(personnel):
        return assessment
    framework_id = preferred_framework_id or ensure_framework(db).id
    assessment = ContractSelfAssessment(
        personnel_id=personnel.id,
        contract_start_date=personnel.contract_start_date,
        contract_end_date=personnel.contract_end_date,
        indicator_framework_id=framework_id,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


@router.get("/self-assessment/current", response_model=CurrentSelfAssessmentRead)
def get_current_self_assessment(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_own_personnel),
    _module: None = Depends(require_module("self_assessment")),
) -> CurrentSelfAssessmentRead:
    personnel = db.get(Personnel, current_user.personnel_id)
    if personnel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    assessment = _ensure_current_assessment(db, personnel, current_user.role)
    return _assessment_read(db, personnel, current_user.role, assessment)


def _submit_current_self_assessment(
    payload: SelfAssessmentSubmit,
    db: Session,
    current_user: CurrentUser,
    preferred_framework_id: int | None = None,
) -> CurrentSelfAssessmentRead:
    personnel = db.scalar(
        select(Personnel).where(Personnel.id == current_user.personnel_id).with_for_update(of=Personnel)
    )
    if personnel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    if not may_self_assess(current_user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="برای این نقش خودارزیابی تعریف نشده است",
        )
    if not contract_is_open(personnel):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="خودارزیابی فقط در بازهٔ قرارداد فعال قابل ثبت است",
        )

    assessment = assessment_for_contract(db, personnel.id, personnel.contract_start_date)
    if assessment is not None and assessment.submitted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="خودارزیابی این قرارداد قبلاً ثبت شده و قابل تغییر نیست",
        )
    if assessment is None:
        framework_id = preferred_framework_id or ensure_framework(db).id
        assessment = ContractSelfAssessment(
            personnel_id=personnel.id,
            contract_start_date=personnel.contract_start_date,
            contract_end_date=personnel.contract_end_date,
            indicator_framework_id=framework_id,
        )
        db.add(assessment)
        db.flush()
    else:
        assessment.contract_end_date = personnel.contract_end_date

    allowed = indicator_ids_for_assessment(db, assessment)
    seen: set[int] = set()
    for item in payload.scores:
        if item.indicator_id not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"شاخص #{item.indicator_id} جزو شاخص‌های این خودارزیابی نیست",
            )
        if item.indicator_id in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="هر شاخص فقط یک‌بار می‌تواند امتیاز بگیرد",
            )
        seen.add(item.indicator_id)
    if not allowed or seen != allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای ثبت نهایی باید به همهٔ شاخص‌ها امتیاز بدهید",
        )

    for item in payload.scores:
        db.add(
            ContractSelfAssessmentScore(
                contract_self_assessment_id=assessment.id,
                indicator_id=item.indicator_id,
                score=item.score,
                note=item.note,
            )
        )
    assessment.submitted_at = datetime.now(UTC)
    assessment.submitted_by_user_id = current_user.id
    assessment.note = payload.note
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="self_assessment_submitted",
        new_value={
            "personnel_id": personnel.id,
            "contract_self_assessment_id": assessment.id,
            "contract_start_date": personnel.contract_start_date.isoformat(),
            "scored_indicators": len(payload.scores),
        },
    )
    hr_ids = list(
        db.scalars(
            select(User.id).where(
                User.role == UserRole.hr,
                User.is_active.is_(True),
                User.id != current_user.id,
            )
        )
    )
    notify(
        db,
        hr_ids,
        type_="self_assessment_submitted",
        message=f"{personnel.full_name} خودارزیابی قرارداد جاری خود را ثبت کرد",
        link=f"/hr/personnel?self-assessment={personnel.id}",
    )
    db.commit()
    db.refresh(assessment)
    return _assessment_read(db, personnel, current_user.role, assessment)


@router.post("/self-assessment", response_model=CurrentSelfAssessmentRead)
def submit_current_self_assessment(
    payload: SelfAssessmentSubmit,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_own_personnel),
    _module: None = Depends(require_module("self_assessment")),
) -> CurrentSelfAssessmentRead:
    return _submit_current_self_assessment(payload, db, current_user)


# Compatibility for an already-open browser tab using the old case-owned URLs.
@router.get("/evaluations/{evaluation_id}/self-assessment", response_model=SelfAssessmentRead)
def get_my_self_assessment(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_own_personnel),
) -> SelfAssessmentRead:
    record = _my_record_or_404(db, evaluation_id, current_user)
    personnel = db.get(Personnel, current_user.personnel_id)
    if personnel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    assessment = _ensure_current_assessment(db, personnel, current_user.role, record.indicator_framework_id)
    return _assessment_read(db, personnel, current_user.role, assessment)


@router.post("/evaluations/{evaluation_id}/self-assessment", response_model=SelfAssessmentRead)
def submit_self_assessment(
    evaluation_id: int,
    payload: SelfAssessmentSubmit,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_own_personnel),
    _module: None = Depends(require_module("self_assessment")),
) -> CurrentSelfAssessmentRead:
    record = _my_record_or_404(db, evaluation_id, current_user)
    return _submit_current_self_assessment(payload, db, current_user, record.indicator_framework_id)


def _my_record_or_404(db: Session, evaluation_id: int, current_user: CurrentUser) -> EvaluationRecord:
    """پروندهٔ خود کارمند، یا ۴۰۴.

    پرونده دیگران عمداً 404 برمی‌گردد (نه 403) تا وجودش هم لو نرود.
    """
    record = db.get(EvaluationRecord, evaluation_id)
    if record is None or current_user.personnel_id is None or record.subject_personnel_id != current_user.personnel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ارزیابی یافت نشد")
    return record


@router.post("/evaluations/{evaluation_id}/object", response_model=MyEvaluationRead)
def file_objection(
    evaluation_id: int,
    payload: ObjectionRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_own_personnel),
) -> EvaluationRecord:
    """ثبت اعتراض رسمی به نتیجهٔ نهایی.

    «رؤیت» فقط ثبت می‌کند که فرد نتیجه را *دید*، نه این‌که پذیرفت. بدون این مسیر،
    سامانه هیچ جایی برای مخالفت او ندارد و در هر بازبینی حقوقی پاسخِ «کارمند چه
    گفت؟» می‌شود «هیچ‌چیز ثبت نشده».

    نتیجه را تغییر نمی‌دهد: سند نهایی و هشِ آن دست‌نخورده می‌مانند. اعتراض یک رکورد
    موازی است که HR باید به آن رسیدگی و پاسخش را ثبت کند.
    """
    record = _my_record_or_404(db, evaluation_id, current_user)

    if record.status != EvaluationStatus.finalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="فقط به ارزیابی نهایی‌شده می‌توان اعتراض کرد",
        )
    if record.acknowledged_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ابتدا مشاهدهٔ نتیجه را ثبت کنید، سپس در صورت لزوم اعتراض بگذارید",
        )
    if record.objection_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای این ارزیابی قبلاً اعتراض ثبت شده است",
        )

    deadline = record.acknowledged_at + timedelta(days=settings.objection_window_days)
    if datetime.now(UTC) > deadline:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"مهلت اعتراض ({settings.objection_window_days} روز پس از مشاهدهٔ نتیجه) به پایان رسیده است"),
        )

    record.objection_at = datetime.now(UTC)
    record.objection_reason = payload.reason
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="evaluation_objection_filed",
        evaluation_record_id=record.id,
        new_value={"reason": payload.reason},
    )

    from app.models.user import User

    hr_ids = list(db.scalars(select(User.id).where(User.role == UserRole.hr, User.is_active.is_(True))))
    notify(
        db,
        hr_ids,
        type_="evaluation_objection_filed",
        message=(f"کارمند {record.subject.full_name} به نتیجهٔ پروندهٔ {record.evaluation_code} اعتراض ثبت کرد"),
        evaluation_record_id=record.id,
        link=f"/evaluations/{record.id}",
    )

    db.commit()
    db.refresh(record)
    return record


@router.post("/evaluations/{evaluation_id}/acknowledge", response_model=MyEvaluationRead)
def acknowledge_evaluation(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_own_personnel),
) -> EvaluationRecord:
    record = _my_record_or_404(db, evaluation_id, current_user)
    if record.status != EvaluationStatus.finalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="فقط ارزیابی نهایی‌شده را می‌توان مشاهده‌شده ثبت کرد",
        )
    if record.acknowledged_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="مشاهدهٔ این ارزیابی قبلاً ثبت شده است",
        )

    record.acknowledged_at = datetime.now(UTC)
    record.acknowledged_by_user_id = current_user.id
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="evaluation_acknowledged",
        evaluation_record_id=record.id,
        new_value={"acknowledged_at": record.acknowledged_at.isoformat()},
    )

    from app.models.user import User

    hr_ids = list(db.scalars(select(User.id).where(User.role == UserRole.hr, User.is_active.is_(True))))
    notify(
        db,
        hr_ids,
        type_="evaluation_acknowledged",
        message=(f"کارمند {record.subject.full_name} نتیجه پرونده {record.evaluation_code} را دید"),
        evaluation_record_id=record.id,
        link=f"/evaluations/{record.id}",
    )

    db.commit()
    db.refresh(record)
    return record
