"""«کارنامه من»: نمای شخصی کارمند از نتایج نهایی ارزیابی خودش + رؤیت رسمی.

کارمند (نقش employee) به پرونده کامل دسترسی ندارد — شواهد و کامنت‌های داخلی
زنجیره تأیید خصوصی می‌مانند؛ فقط خلاصه نتیجه نهایی‌شده را می‌بیند و با «رؤیت شد»
به‌صورت رسمی و قابل‌استناد (audit) تأیید می‌کند که نتیجه به او ابلاغ شده است.
"""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.config import settings
from app.db.session import get_db
from app.models.enums import EvaluationStatus, ImprovementPlanStatus, UserRole
from app.models.evaluation import EvaluationRecord
from app.models.improvement_plan import ImprovementPlan
from app.models.indicator import Indicator
from app.models.self_assessment import SelfAssessmentScore
from app.schemas.auth import CurrentUser
from app.schemas.evaluation import (
    MyEvaluationPage,
    MyEvaluationRead,
    MyOpenEvaluation,
    ObjectionRequest,
    SelfAssessmentRead,
    SelfAssessmentScoreRead,
    SelfAssessmentSubmit,
)
from app.schemas.improvement_plan import ImprovementPlanDetail
from app.services.audit import log_event
from app.services.notifications import notify
from app.services.workflow import IS_OPEN_RECORD

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("/evaluations", response_model=MyEvaluationPage)
def my_evaluations(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.employee)),
) -> MyEvaluationPage:
    if current_user.personnel_id is None:
        return MyEvaluationPage(total=0, items=[])
    query = select(EvaluationRecord).where(
        EvaluationRecord.subject_personnel_id == current_user.personnel_id,
        EvaluationRecord.status == EvaluationStatus.finalized,
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.order_by(EvaluationRecord.finalized_at.desc())))
    return MyEvaluationPage(
        total=total, items=[MyEvaluationRead.model_validate(r) for r in items]
    )


@router.get("/evaluations/open", response_model=list[MyOpenEvaluation])
def my_open_evaluation(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.employee)),
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
    return [MyOpenEvaluation.model_validate(r) for r in records]


@router.get("/improvement-plans", response_model=list[ImprovementPlanDetail])
def my_improvement_plans(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.employee)),
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


# خودارزیابی فقط تا پیش از قطعی‌شدن نمرهٔ ارزیاب معنا دارد: بعد از آن دیگر «دیدگاه
# مستقل» نیست، واکنش به نمره است. مسیر عادی در draft، مسیر «مدیر» در hr_approved
# (که معاونت خودش نمره‌دهندهٔ اول است).
_SELF_ASSESSMENT_OPEN_STATUSES = frozenset(
    {EvaluationStatus.draft, EvaluationStatus.hr_approved}
)


@router.get("/evaluations/{evaluation_id}/self-assessment", response_model=SelfAssessmentRead)
def get_my_self_assessment(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.employee)),
) -> SelfAssessmentRead:
    record = _my_record_or_404(db, evaluation_id, current_user)
    return _self_assessment_of(db, record)


@router.post("/evaluations/{evaluation_id}/self-assessment", response_model=SelfAssessmentRead)
def submit_self_assessment(
    evaluation_id: int,
    payload: SelfAssessmentSubmit,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.employee)),
) -> SelfAssessmentRead:
    """ثبت خودارزیابی — نظر خودِ فرد پیش از آن‌که نمرهٔ ارزیاب قطعی شود.

    اختیاری و غیرمسدودکننده است: اگر کارمند چیزی ثبت نکند، گردش‌کار مثل قبل جلو
    می‌رود. مرحلهٔ مسدودکننده یعنی یک کارمندِ بی‌پاسخ کل پرونده را متوقف می‌کند —
    همان بن‌بستی که تازه از گردش‌کار حذف شد.

    یک‌بار ثبت می‌شود و قفل می‌ماند: اگر بعد از دیدن نمرهٔ ارزیاب قابل ویرایش بود،
    دیگر دیدگاه مستقلی نبود.
    """
    record = _my_record_or_404(db, evaluation_id, current_user)

    if record.status not in _SELF_ASSESSMENT_OPEN_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="مهلت خودارزیابی گذشته است؛ نمرهٔ ارزیاب قبلاً ثبت شده",
        )
    if record.self_assessment_submitted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="خودارزیابی شما قبلاً ثبت شده و قابل تغییر نیست",
        )

    active = {i.id for i in db.scalars(select(Indicator).where(Indicator.is_active.is_(True)))}
    seen: set[int] = set()
    for item in payload.scores:
        if item.indicator_id not in active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"شاخص #{item.indicator_id} معتبر یا فعال نیست",
            )
        if item.indicator_id in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="هر شاخص فقط یک‌بار می‌تواند امتیاز بگیرد",
            )
        seen.add(item.indicator_id)
        db.add(
            SelfAssessmentScore(
                evaluation_record_id=record.id,
                indicator_id=item.indicator_id,
                score=item.score,
                note=item.note,
            )
        )

    record.self_assessment_submitted_at = datetime.now(UTC)
    record.self_assessment_note = payload.note
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="self_assessment_submitted",
        evaluation_record_id=record.id,
        new_value={"scored_indicators": len(payload.scores)},
    )

    # نمره‌دهندهٔ اول باید بداند دیدگاه فرد رسیده، وگرنه بی‌آنکه ببیندش نمره می‌دهد
    evaluator_id = record.unit_supervisor_user_id or record.deputy_user_id
    notify(
        db,
        [evaluator_id],
        type_="self_assessment_submitted",
        message=(
            f"{record.subject.full_name} خودارزیابی‌اش را برای پروندهٔ "
            f"{record.evaluation_code} ثبت کرد"
        ),
        evaluation_record_id=record.id,
        link=f"/evaluations/{record.id}",
    )

    db.commit()
    db.refresh(record)
    return _self_assessment_of(db, record)


def _self_assessment_of(db: Session, record: EvaluationRecord) -> SelfAssessmentRead:
    rows = db.scalars(
        select(SelfAssessmentScore).where(
            SelfAssessmentScore.evaluation_record_id == record.id
        )
    )
    return SelfAssessmentRead(
        submitted_at=record.self_assessment_submitted_at,
        note=record.self_assessment_note,
        scores=[SelfAssessmentScoreRead.model_validate(r) for r in rows],
    )


def _my_record_or_404(
    db: Session, evaluation_id: int, current_user: CurrentUser
) -> EvaluationRecord:
    """پروندهٔ خود کارمند، یا ۴۰۴.

    پرونده دیگران عمداً 404 برمی‌گردد (نه 403) تا وجودش هم لو نرود.
    """
    record = db.get(EvaluationRecord, evaluation_id)
    if (
        record is None
        or current_user.personnel_id is None
        or record.subject_personnel_id != current_user.personnel_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ارزیابی یافت نشد")
    return record


@router.post("/evaluations/{evaluation_id}/object", response_model=MyEvaluationRead)
def file_objection(
    evaluation_id: int,
    payload: ObjectionRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.employee)),
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
            detail="ابتدا نتیجه را رؤیت کنید، سپس در صورت لزوم اعتراض ثبت کنید",
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
            detail=(
                f"مهلت اعتراض ({settings.objection_window_days} روز پس از رؤیت) "
                "به پایان رسیده است"
            ),
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

    hr_ids = list(
        db.scalars(select(User.id).where(User.role == UserRole.hr, User.is_active.is_(True)))
    )
    notify(
        db,
        hr_ids,
        type_="evaluation_objection_filed",
        message=(
            f"کارمند {record.subject.full_name} به نتیجهٔ پروندهٔ "
            f"{record.evaluation_code} اعتراض ثبت کرد"
        ),
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
    current_user: CurrentUser = Depends(require_roles(UserRole.employee)),
) -> EvaluationRecord:
    record = _my_record_or_404(db, evaluation_id, current_user)
    if record.status != EvaluationStatus.finalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="فقط ارزیابی نهایی‌شده قابل رؤیت است",
        )
    if record.acknowledged_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این ارزیابی قبلاً رؤیت شده است",
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

    hr_ids = list(
        db.scalars(
            select(User.id).where(User.role == UserRole.hr, User.is_active.is_(True))
        )
    )
    notify(
        db,
        hr_ids,
        type_="evaluation_acknowledged",
        message=(
            f"کارمند {record.subject.full_name} نتیجه پرونده "
            f"{record.evaluation_code} را رؤیت کرد"
        ),
        evaluation_record_id=record.id,
        link=f"/evaluations/{record.id}",
    )

    db.commit()
    db.refresh(record)
    return record
