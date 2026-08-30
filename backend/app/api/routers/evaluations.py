import secrets
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_chain_stage, require_roles
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.enums import (
    CommentStage,
    EvaluationStatus,
    PeriodStatus,
    PersonnelStatus,
    UserRole,
)
from app.models.evaluation import EvaluationComment, EvaluationRecord, EvaluationScore
from app.models.evaluation_access import EvaluationAccess
from app.models.evaluation_period import EvaluationPeriod
from app.models.indicator_framework import IndicatorFramework
from app.models.personnel import Personnel
from app.models.self_assessment import SelfAssessmentScore
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.schemas.evaluation import (
    CancelRequest,
    CommentCreate,
    CommentRead,
    EvaluationCreate,
    EvaluationDetail,
    EvaluationPage,
    EvaluationRead,
    EvaluatorCommentUpdate,
    HrHandover,
    ObjectionResolution,
    ReturnRequest,
    ScoreRead,
    ScoresUpsert,
    SelfAssessmentRead,
    SelfAssessmentScoreRead,
    SpecialScoreUpdate,
    StageOwnerReassign,
)
from app.services.audit import log_event
from app.services.documents import archive_final_pdf, archive_final_pdf_detached
from app.services.evaluation import inactive_seat_labels, next_evaluation_code, validate_bonus
from app.services.excel import build_evaluations_workbook
from app.services.indicator_framework import (
    ensure_framework,
    indicator_ids_for_record,
    indicators_for_record,
)
from app.services.notifications import notify, notify_stage_owner_reassigned
from app.services.pdf import weasyprint_available
from app.services.scoring_scheme import active_scheme, rules_for_record
from app.services.self_assessment import may_view as may_view_self_assessment
from app.services.self_evaluation import (
    ensure_chain_stages_are_not_redundant,
    ensure_evaluators_are_not_the_subject,
    ensure_not_deciding_about_oneself,
)
from app.services.snapshot import build_final_snapshot
from app.services.workflow import (
    IS_OPEN_RECORD,
    OPEN_STATUSES,
    apply_transition,
    finalize_scoring,
    is_manager_path,
    may_act_at,
)

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


def _get_record_or_404(db: Session, evaluation_id: int) -> EvaluationRecord:
    record = db.get(EvaluationRecord, evaluation_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ارزیابی یافت نشد")
    return record


def _get_record_or_404_for_update(db: Session, evaluation_id: int) -> EvaluationRecord:
    """مثل _get_record_or_404 اما با قفل ردیف (SELECT ... FOR UPDATE) — مخصوص
    گذارهای گردش‌کار (submit/hr-approve/deputy-approve/ceo-finalize/return).
    بدون این قفل، دو درخواست هم‌زمان (مثلاً دوبار کلیک روی «تأیید») می‌توانستند
    هر دو از ensure_transition_allowed عبور کنند پیش از آنکه هرکدام commit شود؛
    قفل ردیف دومین درخواست را تا commit اولی معطل نگه می‌دارد تا وضعیتِ به‌روزشده
    را ببیند و با خطای تمیز رد شود، نه یک race بی‌صدا.

    subject (Personnel) با lazy="joined" همیشه eager-join می‌شود؛ Postgres قفل
    FOR UPDATE را روی سمت nullable یک outer join نمی‌پذیرد، پس صراحتاً فقط خودِ
    evaluation_records قفل می‌شود (of=EvaluationRecord ⇒ «FOR UPDATE OF …»)."""
    record = db.scalar(
        select(EvaluationRecord)
        .where(EvaluationRecord.id == evaluation_id)
        .with_for_update(of=EvaluationRecord)
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ارزیابی یافت نشد")
    return record


def _is_the_scorer(record: EvaluationRecord, current_user: CurrentUser) -> bool:
    """آیا این کاربر همان کسی است که *الان* باید به این پرونده نمره بدهد.

    سه جا (ثبت امتیاز، نظر ارزیاب، امتیاز ویژه) هر کدام کپیِ خودشان از این شرط
    را داشتند و هر سه با دو شرطِ تقریباً یکسان `or` می‌شدند. حالا که مسیر «مدیر»
    هم از `draft` شروع می‌شود، تفاوتِ دو مسیر فقط در *کیست* است، نه در وضعیت —
    و همین یک تابع کافی است.
    """
    if record.status is not EvaluationStatus.draft:
        return False
    manager_path = is_manager_path(record)
    stage_role = UserRole.deputy if manager_path else UserRole.unit_supervisor
    scorer_id = record.deputy_user_id if manager_path else record.unit_supervisor_user_id
    return (
        scorer_id is not None
        and current_user.id == scorer_id
        and may_act_at(current_user.role, stage_role)
    )


def _ensure_can_view(record: EvaluationRecord, current_user: CurrentUser) -> None:
    # پیش از هر چیز: موضوعِ پرونده آن را از این‌جا نمی‌بیند. پروندهٔ در جریان
    # شواهدِ ارزیاب را دارد و پنل HR کاملش را نشان می‌دهد؛ کارمندِ منابع انسانی
    # نباید ارزیابیِ خودش را از آن‌جا بخواند. مسیر خودش
    # (`/api/me/evaluations`) جداست و فقط نتیجهٔ نهایی را می‌دهد.
    ensure_not_deciding_about_oneself(record, current_user)
    if current_user.role == UserRole.hr:
        return
    allowed_ids = {record.unit_supervisor_user_id, record.deputy_user_id, record.ceo_user_id}
    if current_user.id not in allowed_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="شما به این ارزیابی دسترسی ندارید"
        )


def _was_returned(db: Session, evaluation_id: int) -> bool:
    """آیا این پرونده در طول عمرش دست‌کم یک‌بار برگشت خورده است. باگ: قبل از این،
    فقط GET لیستی (list_evaluations) این مقدار را محاسبه می‌کرد؛ GET تکی
    (صفحهٔ جزئیات — همان جایی که بازبین/ارزیاب واقعاً روی پرونده کار می‌کند) و
    پاسخ همهٔ endpointهای گردش‌کار (submit/approve/return و...) چون مستقیماً از
    شیء ORM سریالایز می‌شدند، همیشه مقدار پیش‌فرض False پیدانتیک را برمی‌گرداندند —
    یعنی نشان «برگشتی» هرگز در صفحهٔ جزئیات دیده نمی‌شد، حتی برای پرونده‌ای که
    چندبار برگشت خورده بود."""
    return (
        db.scalar(
            select(AuditLog.id)
            .where(
                AuditLog.event_type == "evaluation_returned",
                AuditLog.evaluation_record_id == evaluation_id,
            )
            .limit(1)
        )
        is not None
    )


def _to_read(db: Session, record: EvaluationRecord) -> EvaluationRead:
    return EvaluationRead.model_validate(record).model_copy(
        update={"was_returned": _was_returned(db, record.id)}
    )


def _self_assessment_of(db: Session, record: EvaluationRecord) -> SelfAssessmentRead | None:
    """خودارزیابی فرد، برای نمایش کنار امتیاز ارزیاب.

    None یعنی فرد چیزی ثبت نکرده — که کاملاً مجاز است: خودارزیابی اختیاری و
    غیرمسدودکننده است.
    """
    if record.self_assessment_submitted_at is None:
        return None
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


#: قاعدهٔ نمایش یک جا زندگی می‌کند: `services/self_assessment.may_view`.
#: این‌جا فقط صدا زده می‌شود تا سیاستِ محرمانگی و گاردِ ضدلنگر از هم جدا نیفتند.


def _to_detail(
    db: Session, record: EvaluationRecord, current_user: CurrentUser
) -> EvaluationDetail:
    framework = (
        db.get(IndicatorFramework, record.indicator_framework_id)
        if record.indicator_framework_id is not None
        else None
    )
    return EvaluationDetail.model_validate(record).model_copy(
        update={
            "was_returned": _was_returned(db, record.id),
            "self_assessment": (
                _self_assessment_of(db, record)
                if may_view_self_assessment(record, current_user.role)
                else None
            ),
            "indicator_ids": sorted(indicator_ids_for_record(db, record)),
            "indicator_framework_version": framework.version if framework else None,
        }
    )


def _persisted_scores(db: Session, record: EvaluationRecord) -> list[ScoreRead]:
    """ردیف‌های امتیاز همان‌گونه که ذخیره شدند — با id.

    فرانت پس از ذخیرهٔ خودکار همین را مستقیم در کش می‌نشاند، پس باید *دقیقاً* شکل
    `scores` در EvaluationDetail را داشته باشد؛ وگرنه کش با ردیف‌های ناقص پر می‌شود.
    """
    rows = db.scalars(
        select(EvaluationScore)
        .where(EvaluationScore.evaluation_record_id == record.id)
        .order_by(EvaluationScore.id)
    ).all()
    return [ScoreRead.model_validate(row) for row in rows]


def _replace_scores(db: Session, record: EvaluationRecord, payload: ScoresUpsert) -> list[dict]:
    # شاخص‌های همین پرونده، نه مجموعهٔ فعال (P1-05): ارزیابی که وسط کار سؤالش
    # غیرفعال شده باشد، باید بتواند نمرهٔ همان سؤال را ذخیره کند — وگرنه ذخیرهٔ
    # خودکارِ فرم روی یک ۴۰۰ گیر می‌کند و کارِ نیمه‌تمام از دست می‌رود.
    indicators_by_id = indicators_for_record(db, record)
    indicator_ids_seen = set()
    rows = []
    for item in payload.scores:
        if item.indicator_id not in indicators_by_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"شاخص #{item.indicator_id} جزو شاخص‌های این ارزیابی نیست",
            )
        if item.indicator_id in indicator_ids_seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="هر شاخص فقط یک‌بار می‌تواند امتیاز بگیرد"
            )
        indicator_ids_seen.add(item.indicator_id)
        rows.append(
            {"indicator_id": item.indicator_id, "score": item.score, "evidence_text": item.evidence_text}
        )

    db.query(EvaluationScore).filter(EvaluationScore.evaluation_record_id == record.id).delete()
    for row in rows:
        db.add(EvaluationScore(evaluation_record_id=record.id, **row))
    db.flush()
    return rows


@router.post("", response_model=EvaluationRead, status_code=status.HTTP_201_CREATED)
def create_evaluation(
    payload: EvaluationCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_chain_stage(UserRole.unit_supervisor)
    ),
) -> EvaluationRecord:
    personnel = db.get(Personnel, payload.subject_personnel_id)
    if personnel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    # ارزیابی فقط برای پرسنل فعال معنا دارد؛ داشبورد/دوره‌ها هم فقط فعال‌ها را می‌شمارند.
    if personnel.status != PersonnelStatus.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این پرسنل غیرفعال است؛ امکان شروع ارزیابی برای او وجود ندارد",
        )

    access = db.scalar(
        select(EvaluationAccess).where(EvaluationAccess.personnel_id == personnel.id)
    )
    if access is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دسترسی ارزیابی برای این پرسنل هنوز توسط منابع انسانی تعریف نشده است",
        )

    # صندلی‌های زنجیره باید زنده باشند (M-1): حسابِ غیرفعالِ هر مرحله یعنی
    # پرونده‌ای که هرگز جلو نمی‌رود. وضعیتِ فعال‌بودن هنگام *نوشتنِ* دسترسی
    # سنجیده می‌شود، ولی صندلی ممکن است بعداً مرده باشد — پس هنگام بازکردنِ
    # پرونده هم سنجیده می‌شود.
    inactive_seats = inactive_seat_labels(db, access)
    if inactive_seats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "صندلی‌های غیرفعال در زنجیرهٔ ارزیابی این فرد: "
                + "، ".join(inactive_seats)
                + "؛ ابتدا منابع انسانی باید زنجیره را اصلاح کند"
            ),
        )

    if personnel.is_manager:
        if (
            not may_act_at(current_user.role, UserRole.deputy)
            or current_user.id != access.deputy_user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="فقط معاونت مربوطه می‌تواند ارزیابی این فرد را آغاز کند",
            )
        # مسیر «مدیر»: معاونت خودش نمره‌دهندهٔ اول است، پس پرونده مثل هر پروندهٔ
        # دیگری از `draft` شروع می‌شود — فقط نمره‌دهنده‌اش معاونت است.
        #
        # پیش از این مستقیماً در `hr_approved` ساخته می‌شد، یعنی *مرحلهٔ بررسی
        # منابع انسانی را رد می‌کرد*: معاونت نمره می‌داد و خودش همان نمره را
        # تأیید می‌کرد و پرونده می‌رفت روی میز مدیرعامل. پروندهٔ مدیران —
        # پرامدترین ارزیابی‌های سازمان — با دو چشم بسته می‌شد، در حالی که پروندهٔ
        # یک کارشناس با چهار.
        record_status = EvaluationStatus.draft
        unit_supervisor_user_id = None
    else:
        if access.unit_supervisor_user_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "مسئول واحد برای این پرسنل تعریف نشده است؛ "
                    "ابتدا منابع انسانی باید در بخش دسترسی ارزیابی آن را تعیین کند"
                ),
            )
        if (
            not may_act_at(current_user.role, UserRole.unit_supervisor)
            or current_user.id != access.unit_supervisor_user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="فقط مسئول واحد مربوطه می‌تواند ارزیابی این فرد را آغاز کند",
            )
        record_status = EvaluationStatus.draft
        unit_supervisor_user_id = access.unit_supervisor_user_id

    # هر پرسنل در هر لحظه فقط یک ارزیابی باز (نهایی‌نشده) می‌تواند داشته باشد؛
    # ایندکس یکتای جزئی در دیتابیس هم همین قانون را در برابر race تضمین می‌کند.
    existing_open = db.scalar(
        select(EvaluationRecord).where(
            EvaluationRecord.subject_personnel_id == personnel.id,
            IS_OPEN_RECORD,
        )
    )
    if existing_open is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "برای این پرسنل یک ارزیابی باز (نهایی‌نشده) وجود دارد؛ ابتدا همان پرونده را تکمیل کنید.",
                "evaluation_id": existing_open.id,
            },
        )

    # اگر دوره ارزیابی بازی وجود دارد، پرونده به همان دوره برچسب می‌خورد
    open_period = db.scalar(
        select(EvaluationPeriod).where(EvaluationPeriod.status == PeriodStatus.open)
    )

    # پرونده به طرح نمره‌دهیِ فعالِ همین لحظه مهر می‌خورد (P1-04). از این پس
    # محاسبه‌اش همیشه از همین نسخه می‌خواند، حتی اگر HR فردا وزن‌ها را عوض کند.
    scheme = active_scheme(db)
    # و به نسخهٔ چارچوب شاخص‌ها (P1-05) — یعنی *چه سؤال‌هایی* پرسیده می‌شود.
    framework = ensure_framework(db)

    record = EvaluationRecord(
        evaluation_code=next_evaluation_code(db),
        subject_personnel_id=personnel.id,
        unit_supervisor_user_id=unit_supervisor_user_id,
        deputy_user_id=access.deputy_user_id,
        ceo_user_id=access.ceo_user_id,
        period_id=open_period.id if open_period else None,
        scoring_scheme_id=scheme.id if scheme else None,
        indicator_framework_id=framework.id,
        status=record_status,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError as exc:
        # دو درخواست هم‌زمان: ایندکس یکتای جزئی برنده را مشخص می‌کند. پروندهٔ باز
        # برنده را دوباره واکشی می‌کنیم تا مثل مسیر پیش‌بررسی، evaluation_id را هم
        # برگردانیم و فرانت‌اند بتواند مستقیماً به همان پرونده هدایت کند.
        db.rollback()
        winner = db.scalar(
            select(EvaluationRecord).where(
                EvaluationRecord.subject_personnel_id == personnel.id,
                IS_OPEN_RECORD,
            )
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "برای این پرسنل یک ارزیابی باز (نهایی‌نشده) وجود دارد؛ ابتدا همان پرونده را تکمیل کنید.",
                "evaluation_id": winner.id if winner else None,
            },
        ) from exc
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="status_changed",
        evaluation_record_id=record.id,
        new_value={"status": record_status.value},
    )
    db.commit()
    db.refresh(record)
    return record


def _apply_evaluation_filters(
    query,
    *,
    q: str | None,
    status_filter: EvaluationStatus | None,
    org_unit: str | None,
    created_from: date | None,
    created_to: date | None,
    min_final_pct: float | None,
    max_final_pct: float | None,
    subject_personnel_id: int | None = None,
    was_returned: bool | None = None,
):
    """فیلترهای ترکیب‌پذیر فهرست/خروجی ارزیابی‌ها — یک‌جا تا list و export.xlsx
    همیشه رفتار یکسان داشته باشند (خروجی همان چیزی است که HR فیلتر کرده)."""
    if (
        min_final_pct is not None
        and max_final_pct is not None
        and min_final_pct > max_final_pct
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="کمینهٔ امتیاز نهایی نمی‌تواند از بیشینهٔ آن بزرگ‌تر باشد",
        )
    if (
        created_from is not None
        and created_to is not None
        and created_from > created_to
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ شروع بازه نمی‌تواند بعد از تاریخ پایان آن باشد",
        )
    needs_personnel_join = bool(q) or bool(org_unit)
    if needs_personnel_join:
        query = query.join(Personnel, Personnel.id == EvaluationRecord.subject_personnel_id)

    if status_filter is not None:
        query = query.where(EvaluationRecord.status == status_filter)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            EvaluationRecord.evaluation_code.ilike(pattern)
            | Personnel.full_name.ilike(pattern)
        )
    if org_unit:
        query = query.where(Personnel.org_unit == org_unit)
    if created_from is not None:
        query = query.where(EvaluationRecord.created_at >= created_from)
    if created_to is not None:
        # بازه شامل خودِ روز پایان است (created_at از نوع timestamp است)
        query = query.where(
            EvaluationRecord.created_at < created_to + timedelta(days=1)
        )
    if min_final_pct is not None:
        query = query.where(EvaluationRecord.final_weighted_pct >= min_final_pct)
    if max_final_pct is not None:
        query = query.where(EvaluationRecord.final_weighted_pct <= max_final_pct)
    if subject_personnel_id is not None:
        query = query.where(EvaluationRecord.subject_personnel_id == subject_personnel_id)
    if was_returned is not None:
        # پرونده‌های «برگشتی» یعنی دست‌کم یک رویداد evaluation_returned در سابقهٔ همان
        # پرونده — همان قانونی که در پاسخ (was_returned روی هر آیتم) استفاده می‌شود،
        # اینجا به‌عنوان فیلتر پیش از صفحه‌بندی هم اعمال می‌شود تا HR بتواند
        # «فقط پرونده‌های برگشت‌خورده» را جدا و دقیق مرور کند.
        returned_exists = (
            select(AuditLog.id)
            .where(
                AuditLog.event_type == "evaluation_returned",
                AuditLog.evaluation_record_id == EvaluationRecord.id,
            )
            .exists()
        )
        query = query.where(returned_exists if was_returned else ~returned_exists)
    return query


def scope_evaluations_for_role(query, user: CurrentUser):
    """دامنهٔ دیدِ ارزیابی‌ها به‌صورت allowlist و در یک نقطهٔ مشترک.

    دو نسخه‌کردنِ allowlist یعنی روزی یکی قاعده بگیرد و دیگری نگیرد. نقش
    ناشناخته هیچ — پیش‌فرضِ باز ممنوع.
    """
    if user.role == UserRole.hr:
        return query
    if user.role == UserRole.unit_supervisor:
        return query.where(EvaluationRecord.unit_supervisor_user_id == user.id)
    if user.role == UserRole.deputy:
        return query.where(EvaluationRecord.deputy_user_id == user.id)
    if user.role == UserRole.ceo:
        return query.where(EvaluationRecord.ceo_user_id == user.id)
    if user.role == UserRole.employee:
        # کارمند فقط ارزیابی‌های نهایی‌شده خودش را می‌بیند (رابط اصلی‌اش /api/me است)
        if user.personnel_id is None:
            return query.where(sa_false())
        return query.where(
            EvaluationRecord.subject_personnel_id == user.personnel_id,
            EvaluationRecord.status == EvaluationStatus.finalized,
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="این نقش به پرونده‌های ارزیابی دسترسی ندارد",
    )


def sa_false():
    """شرطِ همیشه-نادرست: فهرستِ تهی با «همه» فرق دارد و با IN () هم یکی نیست."""
    from sqlalchemy import literal

    return literal(False)


@router.get("", response_model=EvaluationPage)
def list_evaluations(
    q: str | None = None,
    status_filter: EvaluationStatus | None = Query(default=None, alias="status"),
    org_unit: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    min_final_pct: float | None = Query(default=None, ge=0, le=100),
    max_final_pct: float | None = Query(default=None, ge=0, le=100),
    subject_personnel_id: int | None = None,
    was_returned: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EvaluationPage:
    query = select(EvaluationRecord)
    # دامنهٔ دید، به‌صورت allowlist و نه زنجیرهٔ if/elif با پیش‌فرضِ باز.
    # نسخهٔ قبلی با `# hr می‌بیند همه را` تمام می‌شد، یعنی *هر* نقشی که در
    # شاخه‌ها نبود همه‌چیز را می‌دید (داستانِ نقش support — P0-03). حالا منطق
    # در `scope_evaluations_for_role` است که دستیار هم از همان استفاده می‌کند؛
    # دو نسخه یعنی روزی یکی قاعده می‌گیرد و دیگری نمی‌گیرد.
    query = scope_evaluations_for_role(query, current_user)

    query = _apply_evaluation_filters(
        query,
        q=q,
        status_filter=status_filter,
        org_unit=org_unit,
        created_from=created_from,
        created_to=created_to,
        min_final_pct=min_final_pct,
        max_final_pct=max_final_pct,
        subject_personnel_id=subject_personnel_id,
        was_returned=was_returned,
    )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(
        db.scalars(
            query.order_by(EvaluationRecord.created_at.desc()).limit(limit).offset(offset)
        )
    )
    # صف بررسی نباید پرونده‌ای که قبلاً برگشت خورده و دوباره ارسال شده را از یک
    # ثبت تازه تشخیص‌نداده نمایش دهد؛ یک کوئری دسته‌ای به‌جای N+1 در audit_log
    returned_ids: set[int] = set()
    if items:
        returned_ids = set(
            db.scalars(
                select(AuditLog.evaluation_record_id)
                .where(
                    AuditLog.event_type == "evaluation_returned",
                    AuditLog.evaluation_record_id.in_([r.id for r in items]),
                )
                .distinct()
            )
        )
    return EvaluationPage(
        total=total,
        items=[
            EvaluationRead.model_validate(r).model_copy(
                update={"was_returned": r.id in returned_ids}
            )
            for r in items
        ],
    )


@router.get("/export.xlsx")
def export_evaluations_excel(
    q: str | None = None,
    status_filter: EvaluationStatus | None = Query(default=None, alias="status"),
    org_unit: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    min_final_pct: float | None = Query(default=None, ge=0, le=100),
    max_final_pct: float | None = Query(default=None, ge=0, le=100),
    was_returned: bool | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> Response:
    """خروجی Excel از ارزیابی‌ها (فقط HR) — همان فیلترهای فهرست را می‌پذیرد تا HR
    دقیقاً همان چیزی را که روی صفحه فیلتر کرده است دریافت کند."""
    query = _apply_evaluation_filters(
        select(EvaluationRecord),
        q=q,
        status_filter=status_filter,
        org_unit=org_unit,
        created_from=created_from,
        created_to=created_to,
        min_final_pct=min_final_pct,
        max_final_pct=max_final_pct,
        was_returned=was_returned,
    )
    records = db.scalars(query.order_by(EvaluationRecord.created_at.desc())).all()
    log_event(db, actor_user_id=current_user.id, event_type="excel_exported")
    db.commit()
    return Response(
        content=build_evaluations_workbook(list(records)),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="evaluations.xlsx"'},
    )


@router.get("/{evaluation_id}", response_model=EvaluationDetail)
def get_evaluation(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EvaluationDetail:
    record = _get_record_or_404(db, evaluation_id)
    _ensure_can_view(record, current_user)
    return _to_detail(db, record, current_user)


@router.put("/{evaluation_id}/scores", response_model=list[ScoreRead])
def upsert_scores(
    evaluation_id: int,
    payload: ScoresUpsert,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ScoreRead]:
    # قفل ردیف مثل خودِ گذارها: بدون آن، بررسی وضعیتِ پایین می‌توانست روی وضعیتی
    # پاس شود که یک submit هم‌زمان دارد عوضش می‌کند، و امتیاز *بعد از*
    # finalize_scoring روی رکورد بنشیند — یعنی امتیازهای ذخیره‌شده با درصد نهاییِ
    # ذخیره‌شده نخوانند. فرانت هم پیش‌نویس امتیاز را حین تایپ auto-save می‌کند،
    # پس این پنجره در عمل باز است، نه تئوریک.
    record = _get_record_or_404_for_update(db, evaluation_id)

    if not _is_the_scorer(record, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="در این مرحله امکان ثبت/ویرایش امتیاز برای شما وجود ندارد",
        )

    rows = _replace_scores(db, record, payload)
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="scores_draft_saved",
        evaluation_record_id=record.id,
        new_value={"scored_indicators": len(rows)},
    )
    saved = _persisted_scores(db, record)
    db.commit()
    return saved


@router.patch("/{evaluation_id}/evaluator-comment", response_model=EvaluationRead)
def set_evaluator_comment(
    evaluation_id: int,
    payload: EvaluatorCommentUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EvaluationRead:
    # همان دلیل upsert_scores: نظر ارزیاب هم روی رکوردی نوشته می‌شود که یک گذار
    # هم‌زمان ممکن است داشته از زیرش عوضش کند.
    record = _get_record_or_404_for_update(db, evaluation_id)
    # نمره‌دهندهٔ اول این نظر را ثبت می‌کند — در هر دو مسیر، در مرحلهٔ نمره‌دهی.
    if not _is_the_scorer(record, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="امکان ثبت نظر در این مرحله وجود ندارد"
        )
    record.evaluator_comment = payload.evaluator_comment
    db.commit()
    db.refresh(record)
    return _to_read(db, record)


@router.patch("/{evaluation_id}/special-score", response_model=EvaluationRead)
def set_special_score(
    evaluation_id: int,
    payload: SpecialScoreUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EvaluationRead:
    """امتیاز ویژه: نمرهٔ اختیاری بابت کاری خارج از شرح وظایف.

    همان کسی می‌تواند ثبتش کند که نمره می‌دهد و جمع‌بندی می‌نویسد — و در همان
    مرحله، پیش از ثبت. بعد از ثبت، امتیاز نهایی حساب شده و پرونده در زنجیرهٔ
    تأیید است؛ تغییر عددِ نتیجه در آن نقطه یعنی تأییدکننده روی چیزی امضا کرده
    که دیگر وجود ندارد. تأییدکننده‌ای که با این عدد موافق نیست، پرونده را
    برمی‌گرداند — همان مسیری که برای هر مخالفتِ دیگری هست.
    """
    record = _get_record_or_404_for_update(db, evaluation_id)
    if not _is_the_scorer(record, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="امکان ثبت امتیاز ویژه در این مرحله برای شما وجود ندارد",
        )

    reason = (payload.bonus_reason or "").strip() or None
    try:
        validate_bonus(payload.bonus_points, reason, rules_for_record(db, record))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    previous = {
        "bonus_points": float(record.bonus_points) if record.bonus_points is not None else None,
        "bonus_reason": record.bonus_reason,
    }
    record.bonus_points = payload.bonus_points
    # صفر یعنی امتیاز ویژه‌ای در کار نیست؛ دلیلِ باقی‌مانده از مقدار قبلی فقط
    # گمراه‌کننده است (قید دیتابیس هم اجازه‌اش را نمی‌دهد).
    record.bonus_reason = reason if payload.bonus_points > 0 else None

    # این یک تعدیلِ دستی روی نتیجهٔ یک تصمیم رسمی است — دقیقاً همان چیزی که
    # لاگ ممیزی برایش هست. مقدار قبلی هم ثبت می‌شود تا «چه شد» قابل بازسازی باشد.
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="special_score_set",
        evaluation_record_id=record.id,
        old_value=previous,
        new_value={"bonus_points": payload.bonus_points, "bonus_reason": record.bonus_reason},
    )
    db.commit()
    db.refresh(record)
    return _to_read(db, record)


@router.post("/{evaluation_id}/submit", response_model=EvaluationRead)
def submit_evaluation(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_chain_stage(UserRole.unit_supervisor)),
) -> EvaluationRead:
    """ثبت نهاییِ نمره‌دهی — پایانِ کارِ نمره‌دهندهٔ اول، در هر دو مسیر.

    گاردِ نقش روی «مسئول واحد» است و برای معاونت هم می‌گذرد (`may_act_at`)؛
    مالکیت واقعی را خودِ گذار می‌سنجد.
    """
    record = _get_record_or_404_for_update(db, evaluation_id)
    # در مسیر «مدیر» نمره‌دهنده معاونت است، پس گذارِ دیگری با همان مقصد لازم
    # است. محاسبهٔ نتیجه در هر دو مسیر همین‌جا انجام می‌شود — جایی که نمره‌دهی
    # تمام می‌شود — نه در تأیید معاونت.
    action = "manager_submit" if is_manager_path(record) else "submit"
    apply_transition(
        db, record, action, current_user,
        before=lambda: finalize_scoring(db, record, current_user),
    )
    db.commit()
    db.refresh(record)
    return _to_read(db, record)


@router.post("/{evaluation_id}/hr-approve", response_model=EvaluationRead)
def hr_approve(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> EvaluationRead:
    record = _get_record_or_404_for_update(db, evaluation_id)
    # اقدام HR روی پروندهٔ خودش. مسیر گذارها از `_ensure_can_view` نمی‌گذرد،
    # پس گارد این‌جا صریح است نه ضمنی.
    ensure_not_deciding_about_oneself(record, current_user)
    # در مسیر «مدیر»، تأیید منابع انسانی پرونده را مستقیم روی میز مدیرعامل
    # می‌گذارد: مرحلهٔ معاونت مصرف شده، چون خودش نمره داده است.
    action = "hr_approve_manager" if is_manager_path(record) else "hr_approve"
    apply_transition(db, record, action, current_user)
    db.commit()
    db.refresh(record)
    return _to_read(db, record)


@router.post("/{evaluation_id}/deputy-approve", response_model=EvaluationRead)
def deputy_approve(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_chain_stage(UserRole.deputy)),
) -> EvaluationRead:
    record = _get_record_or_404_for_update(db, evaluation_id)
    # محاسبهٔ نتیجه دیگر این‌جا انجام نمی‌شود: در مسیر «مدیر» هم نمره‌دهی با
    # `submit` تمام می‌شود، و پروندهٔ آن مسیر هرگز به `hr_approved` — تنها
    # وضعیتِ ورودیِ این گذار — نمی‌رسد.
    apply_transition(db, record, "deputy_approve", current_user)
    db.commit()
    db.refresh(record)
    return _to_read(db, record)


@router.post("/{evaluation_id}/ceo-finalize", response_model=EvaluationRead)
def ceo_finalize(
    evaluation_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_chain_stage(UserRole.ceo)),
) -> EvaluationRead:
    record = _get_record_or_404_for_update(db, evaluation_id)

    def _before() -> None:
        record.finalized_at = datetime.now(UTC)
        record.final_snapshot = build_final_snapshot(db, record)
        # توکن تصادفی صفحهٔ تأیید عمومی؛ evaluation_code ترتیبی است و نباید کلید
        # جست‌وجوی یک endpoint بدون احراز هویت باشد (قابل شمارش/enumeration)
        record.verify_token = secrets.token_urlsafe(24)

    apply_transition(db, record, "ceo_finalize", current_user, before=_before)
    db.commit()
    db.refresh(record)
    # سند PDF *پس از* ارسال پاسخ ساخته می‌شود (P2-05). قبلاً همین‌جا و به‌صورت
    # همزمان رندر می‌شد، یعنی WeasyPrint — یک کتابخانهٔ بومیِ CPU-محور — روی مسیر
    # تأخیرِ مهم‌ترین اقدام سامانه بود و کندشدنِ رندر به «نهایی‌سازی ناموفق» ترجمه
    # می‌شد. حالا نهایی‌سازی قطعی است و سند دنبالش می‌آید؛ اگر این کار پس‌زمینه هم
    # شکست بخورد (ری‌استارت پروسه، نبودِ کتابخانه)، جاروی زمان‌بند آن را می‌گیرد و
    # مسیر دانلود هم در لحظه می‌سازدش. آرشیو idempotent است، پس تکرار بی‌خطر است.
    background_tasks.add_task(archive_final_pdf_detached, record.id)
    return _to_read(db, record)


_RETURN_ACTION_BY_ROLE = {
    UserRole.hr: ("hr_return", CommentStage.hr_review),
    UserRole.deputy: ("deputy_return", CommentStage.deputy_review),
    UserRole.ceo: ("ceo_return", CommentStage.ceo_final),
}


@router.post("/{evaluation_id}/return", response_model=EvaluationRead)
def return_evaluation(
    evaluation_id: int,
    payload: ReturnRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles(UserRole.hr, UserRole.deputy, UserRole.ceo)
    ),
) -> EvaluationRead:
    """برگشت پرونده یک مرحله به عقب با ذکر دلیل اجباری؛ امتیازهای قبلی حفظ می‌شوند."""
    record = _get_record_or_404_for_update(db, evaluation_id)
    action, comment_stage = _RETURN_ACTION_BY_ROLE[current_user.role]

    if action == "ceo_return" and is_manager_path(record):
        # در این مسیر مرحلهٔ معاونت مصرف شده؛ پرونده به صف منابع انسانی برمی‌گردد.
        action = "ceo_return_manager"

    if action == "deputy_return" and is_manager_path(record):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="در مسیر «مدیر» مرحله قبلی وجود ندارد؛ معاونت خودش نمره‌دهنده اول است",
        )

    def _before() -> None:
        # دلیل برگشت هم به‌صورت کامنت قابل‌مشاهده در پرونده ثبت می‌شود و هم در audit
        db.add(
            EvaluationComment(
                evaluation_record_id=record.id,
                commenter_user_id=current_user.id,
                stage=comment_stage,
                comment_text=f"برگشت پرونده — دلیل: {payload.reason}",
            )
        )
        log_event(
            db,
            actor_user_id=current_user.id,
            event_type="evaluation_returned",
            evaluation_record_id=record.id,
            new_value={"reason": payload.reason},
        )

    apply_transition(db, record, action, current_user, before=_before)
    db.commit()
    db.refresh(record)
    return _to_read(db, record)


@router.post("/{evaluation_id}/cancel", response_model=EvaluationRead)
def cancel_evaluation(
    evaluation_id: int,
    payload: CancelRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> EvaluationRead:
    """لغو پروندهٔ باز با دلیل اجباری — تنها راه خروج از پروندهٔ گیرکرده.

    بدون این، پرونده‌ای که تأییدکننده‌اش از سازمان رفته هرگز کامل نمی‌شد و ایندکس
    یکتای جزئی هم اجازهٔ ساخت پروندهٔ جایگزین نمی‌داد؛ آن پرسنل عملاً برای همیشه
    غیرقابل‌ارزیابی می‌ماند و تنها درمانش SQL دستی روی پروداکشن بود.
    """
    record = _get_record_or_404_for_update(db, evaluation_id)
    # اقدام HR روی پروندهٔ خودش (همان دلیل بالا).
    ensure_not_deciding_about_oneself(record, current_user)

    def _before() -> None:
        # دلیل هم به‌صورت کامنت در خود پرونده می‌ماند و هم در audit — تصمیم است، نه پاک‌کردن.
        db.add(
            EvaluationComment(
                evaluation_record_id=record.id,
                commenter_user_id=current_user.id,
                stage=CommentStage.hr_review,
                comment_text=f"لغو پرونده — دلیل: {payload.reason}",
            )
        )
        log_event(
            db,
            actor_user_id=current_user.id,
            event_type="evaluation_cancelled",
            evaluation_record_id=record.id,
            old_value={"status": record.status.value},
            new_value={"reason": payload.reason},
        )

    apply_transition(db, record, "cancel", current_user, before=_before)
    db.commit()
    db.refresh(record)
    return _to_read(db, record)


@router.post("/{evaluation_id}/hr-claim", response_model=EvaluationRead)
def hr_claim(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> EvaluationRead:
    """برداشتن یک پروندهٔ بی‌مالک از صف مشترک منابع انسانی.

    اقدام روی پرونده (تأیید/برگشت) هم به‌طور ضمنی همین کار را می‌کند؛ این endpoint
    برای وقتی است که کسی می‌خواهد *پیش از* اقدام مسئولیتش را اعلام کند تا دو نفر
    هم‌زمان روی یک پرونده کار نکنند.
    """
    record = _get_record_or_404_for_update(db, evaluation_id)
    # اقدام HR روی پروندهٔ خودش (همان دلیل بالا).
    ensure_not_deciding_about_oneself(record, current_user)

    if record.status not in OPEN_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="فقط پروندهٔ باز می‌تواند مسئول منابع انسانی بگیرد",
        )
    if record.hr_user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"این پرونده از قبل در اختیار «{record.hr_username}» است؛ "
                "برای جابه‌جایی از «واگذاری» استفاده کنید."
            ),
        )

    record.hr_user_id = current_user.id
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="hr_case_claimed",
        evaluation_record_id=record.id,
        new_value={"hr_user_id": current_user.id, "implicit": False},
    )
    db.commit()
    db.refresh(record)
    return _to_read(db, record)


@router.post("/{evaluation_id}/hr-handover", response_model=EvaluationRead)
def hr_handover(
    evaluation_id: int,
    payload: HrHandover,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> EvaluationRead:
    """واگذاری مسئولیتِ HR به کاربر دیگری از منابع انسانی، با دلیل و ثبت در audit.

    محدودیت آگاهانه: هر کاربر HR می‌تواند این کار را بکند، چون هنوز نقش «سرپرست HR»
    وجود ندارد. پس این یک قفل سخت نیست — یک زنجیرهٔ مسئولیتِ قابل ردیابی است، که
    خودش از وضعیت قبلی («هر HR روی هر پرونده، بدون هیچ ردی») بسیار بهتر است.
    تفکیک واقعی نقش‌های HR گام میان‌مدت همین یافته است.
    """
    record = _get_record_or_404_for_update(db, evaluation_id)
    # اقدام HR روی پروندهٔ خودش (همان دلیل بالا).
    ensure_not_deciding_about_oneself(record, current_user)

    if record.status not in OPEN_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="فقط مسئولِ منابع انسانیِ یک پروندهٔ باز قابل تغییر است",
        )

    new_owner = db.get(User, payload.new_hr_user_id)
    if new_owner is None or not new_owner.is_active or new_owner.role != UserRole.hr:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="کاربر انتخاب‌شده یافت نشد، غیرفعال است، یا نقش منابع انسانی ندارد",
        )
    if new_owner.id == record.hr_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این پرونده از قبل در اختیار همین کاربر است",
        )
    # واگذاری به خودِ ارزیابی‌شونده، دقیقاً همان چیزی است که گارد بالا جلویش را
    # می‌گیرد — فقط از راهِ دیگر. بدون این، هر HRای می‌توانست پروندهٔ یک همکارِ
    # HR را به خودِ او بدهد.
    if new_owner.personnel_id is not None and new_owner.personnel_id == record.subject_personnel_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نمی‌توان پرونده را به کسی واگذار کرد که خودش موضوع همان پرونده است",
        )

    previous_owner_id = record.hr_user_id
    record.hr_user_id = new_owner.id
    db.add(
        EvaluationComment(
            evaluation_record_id=record.id,
            commenter_user_id=current_user.id,
            stage=CommentStage.hr_review,
            comment_text=f"واگذاری مسئولیت منابع انسانی — دلیل: {payload.reason}",
        )
    )
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="hr_case_handed_over",
        evaluation_record_id=record.id,
        old_value={"hr_user_id": previous_owner_id},
        new_value={"hr_user_id": new_owner.id, "reason": payload.reason},
    )
    notify_stage_owner_reassigned(db, record, new_owner.id, "منابع انسانی")
    db.commit()
    db.refresh(record)
    return _to_read(db, record)


@router.post("/{evaluation_id}/resolve-objection", response_model=EvaluationRead)
def resolve_objection(
    evaluation_id: int,
    payload: ObjectionResolution,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> EvaluationRead:
    """ثبت پاسخ منابع انسانی به اعتراض کارمند.

    اعتراضی که کسی موظف به پاسخ‌گویی به آن نباشد، تشریفات است. این endpoint اعتراض
    را می‌بندد و پاسخ را کنار خودِ اعتراض در پرونده ثبت می‌کند.

    نتیجهٔ ارزیابی و سند نهایی عمداً دست‌نخورده می‌مانند: اگر واقعاً باید امتیاز عوض
    شود، مسیرش ارزیابی تازه است نه بازنویسی سندی که هش و امضا دارد.
    """
    record = _get_record_or_404_for_update(db, evaluation_id)
    # اقدام HR روی پروندهٔ خودش (همان دلیل بالا).
    ensure_not_deciding_about_oneself(record, current_user)

    if record.objection_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای این پرونده اعتراضی ثبت نشده است",
        )
    if record.objection_resolved_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="به این اعتراض قبلاً پاسخ داده شده است",
        )

    record.objection_resolved_at = datetime.now(UTC)
    record.objection_resolution = payload.resolution
    record.objection_resolved_by_user_id = current_user.id
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="evaluation_objection_resolved",
        evaluation_record_id=record.id,
        old_value={"objection_reason": record.objection_reason},
        new_value={"resolution": payload.resolution},
    )

    # خودِ معترض باید پاسخ را ببیند، وگرنه اعتراضش در سکوت گم می‌شود
    subject_user_ids = list(
        db.scalars(
            select(User.id).where(
                User.role == UserRole.employee,
                User.personnel_id == record.subject_personnel_id,
                User.is_active.is_(True),
            )
        )
    )
    if subject_user_ids:
        notify(
            db,
            subject_user_ids,
            type_="evaluation_objection_resolved",
            message=f"به اعتراض شما دربارهٔ پروندهٔ {record.evaluation_code} پاسخ داده شد",
            evaluation_record_id=record.id,
            link="/me",
        )

    db.commit()
    db.refresh(record)
    return _to_read(db, record)


_REASSIGNABLE_STAGES: dict[str, tuple[UserRole, str]] = {
    "unit_supervisor_user_id": (UserRole.unit_supervisor, "مسئول واحد"),
    "deputy_user_id": (UserRole.deputy, "معاونت"),
    "ceo_user_id": (UserRole.ceo, "مدیرعامل"),
}


@router.post("/{evaluation_id}/reassign", response_model=EvaluationRead)
def reassign_stage_owner(
    evaluation_id: int,
    payload: StageOwnerReassign,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> EvaluationRead:
    """جایگزینی مسئول یک مرحله روی پروندهٔ باز — بدون از دست رفتن امتیازها.

    عمداً در جدول TRANSITIONS نیست: وضعیت را عوض نمی‌کند، پس گذار نیست. ولی از همان
    قفل ردیف و همان مسیر audit استفاده می‌کند.
    """
    record = _get_record_or_404_for_update(db, evaluation_id)

    if record.status not in OPEN_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="فقط مسئول مراحل یک پروندهٔ باز قابل تغییر است",
        )

    expected_role, stage_label = _REASSIGNABLE_STAGES[payload.stage_field]
    previous_user_id = getattr(record, payload.stage_field)
    if previous_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"این پرونده مرحلهٔ «{stage_label}» ندارد (مسیر «مدیر»)",
        )

    new_user = db.get(User, payload.new_user_id)
    if new_user is None or not new_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"کاربر انتخاب‌شده برای «{stage_label}» یافت نشد یا غیرفعال است",
        )
    if new_user.role != expected_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"کاربر انتخاب‌شده برای «{stage_label}» باید نقش «{stage_label}» داشته باشد",
        )
    # همان نامساوی P0-10: جایگزین نباید خودِ ارزیابی‌شونده باشد.
    ensure_evaluators_are_not_the_subject(
        db, record.subject_personnel_id, [payload.new_user_id]
    )
    # و نباید از قبل در مرحلهٔ دیگری از همین پرونده نشسته باشد. بدون این، همین
    # endpoint راهِ دور زدنِ قید «سه نفر متفاوت» بود: زنجیره درست ساخته می‌شد و
    # بعد یک جابه‌جایی، دو صندلی را به یک نفر می‌داد.
    stages = {
        "unit_supervisor_user_id": record.unit_supervisor_user_id,
        "deputy_user_id": record.deputy_user_id,
        "ceo_user_id": record.ceo_user_id,
    }
    stages[payload.stage_field] = payload.new_user_id
    ensure_chain_stages_are_not_redundant(
        db,
        stages["unit_supervisor_user_id"],
        stages["deputy_user_id"],
        stages["ceo_user_id"],
    )

    setattr(record, payload.stage_field, payload.new_user_id)
    db.add(
        EvaluationComment(
            evaluation_record_id=record.id,
            commenter_user_id=current_user.id,
            stage=CommentStage.hr_review,
            comment_text=f"تغییر مسئول «{stage_label}» — دلیل: {payload.reason}",
        )
    )
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="stage_owner_reassigned",
        evaluation_record_id=record.id,
        old_value={payload.stage_field: previous_user_id},
        new_value={payload.stage_field: payload.new_user_id, "reason": payload.reason},
    )
    notify_stage_owner_reassigned(db, record, new_user.id, stage_label)
    db.commit()
    db.refresh(record)
    return _to_read(db, record)


@router.get("/{evaluation_id}/summary.pdf")
def evaluation_summary_pdf(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    record = _get_record_or_404(db, evaluation_id)

    # سوژهٔ پرونده حق دارد سندِ مربوط به خودش را داشته باشد. تا پیش از این تنها
    # کسی که می‌توانست کارنامهٔ هش‌شده و قابل‌تأیید یک نفر را دانلود کند HR بود —
    # یعنی فرد سندی را که دربارهٔ اوست در اختیار نداشت و برای هر استفادهٔ بعدی
    # (اعتراض، پروندهٔ حقوقی، کارفرمای بعدی) باید از سازمان درخواست می‌کرد.
    is_subject = (
        current_user.role == UserRole.employee
        and current_user.personnel_id is not None
        and current_user.personnel_id == record.subject_personnel_id
    )
    if not is_subject:
        _ensure_can_view(record, current_user)
        # سایر نقش‌های زنجیره پرونده را می‌بینند ولی سند رسمی را دانلود نمی‌کنند.
        if current_user.role != UserRole.hr:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="خروجی PDF فقط برای منابع انسانی و خودِ فرد در دسترس است",
            )

    if record.status != EvaluationStatus.finalized or record.final_snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="ارزیابی هنوز نهایی نشده است"
        )

    # اگر کتابخانه‌های بومی WeasyPrint روی این سرور نصب نباشند، به‌جای خطای مبهم
    # (AttributeError روی سند None) یک پیام واضح ۵۰۰ برمی‌گردانیم.
    if not weasyprint_available():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "تولید PDF روی این سرور در دسترس نیست: کتابخانه‌های سیستمی WeasyPrint "
                "(Pango/Cairo/GDK-PixBuf) نصب نشده‌اند. برای فعال‌سازی چاپ، این کتابخانه‌ها "
                "را روی سرور نصب کنید (راهنما: بخش «چاپ PDF» در README)."
            ),
        )

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="pdf_downloaded",
        evaluation_record_id=record.id,
        # دسترسی خودِ فرد به سندش هم ثبت می‌شود — نه به‌عنوان چیزی مشکوک، بلکه چون
        # زنجیرهٔ حسابرسیِ یک سند رسمی باید کامل باشد و بگوید چه کسی نسخه‌ای دارد.
        new_value={"by_subject": is_subject},
    )

    # سند آرشیوشده را سرو می‌کنیم؛ برای رکوردهای قدیمی (پیش از قابلیت آرشیو) در همین
    # لحظه تولید و ذخیره می‌شود تا از این پس پایدار بماند.
    document = archive_final_pdf(db, record)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="تولید PDF با خطا مواجه شد؛ لطفاً بعداً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.",
        )
    db.commit()

    return Response(
        content=document.pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{record.evaluation_code}.pdf"'
        },
    )


@router.post("/{evaluation_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
def add_comment(
    evaluation_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EvaluationComment:
    record = _get_record_or_404(db, evaluation_id)

    # مسیر «پاسخ threaded»: پاسخ به یک کامنت سطح‌بالای موجود (مثلاً دلیل برگشت پرونده).
    # برخلاف کامنت سطح‌بالا که به مرحلهٔ بازبینی گره خورده، پاسخ را هر مشارکت‌کنندهٔ
    # مجاز به دیدن پرونده می‌تواند ثبت کند تا گفت‌وگوی رفت‌وبرگشتی روی برگشت ممکن شود.
    if payload.parent_comment_id is not None:
        return _add_reply(db, record, payload, current_user)

    stage_by_role = {
        UserRole.hr: (CommentStage.hr_review, EvaluationStatus.submitted, None),
        UserRole.deputy: (CommentStage.deputy_review, EvaluationStatus.hr_approved, record.deputy_user_id),
        UserRole.ceo: (CommentStage.ceo_final, EvaluationStatus.deputy_approved, record.ceo_user_id),
    }
    mapping = stage_by_role.get(current_user.role)
    if mapping is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="نقش شما اجازه ثبت کامنت ندارد")

    comment_stage, required_status, required_user_id = mapping
    if record.status != required_status or (
        required_user_id is not None and current_user.id != required_user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="در این مرحله امکان ثبت کامنت برای شما وجود ندارد"
        )

    comment = EvaluationComment(
        evaluation_record_id=record.id,
        commenter_user_id=current_user.id,
        stage=comment_stage,
        comment_text=payload.comment_text,
    )
    db.add(comment)
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="comment_added",
        evaluation_record_id=record.id,
        new_value={"stage": comment_stage.value},
    )
    db.commit()
    db.refresh(comment)
    return comment


def _add_reply(
    db: Session,
    record: EvaluationRecord,
    payload: CommentCreate,
    current_user: CurrentUser,
) -> EvaluationComment:
    """ثبت یک پاسخ threaded (عمق ۱). فقط کاربرِ مجاز به دیدن پرونده می‌تواند پاسخ دهد؛
    پاسخ به پاسخ مجاز نیست و کامنتِ والد باید به همین پرونده تعلق داشته باشد."""
    _ensure_can_view(record, current_user)

    parent = db.get(EvaluationComment, payload.parent_comment_id)
    if parent is None or parent.evaluation_record_id != record.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="کامنتِ والد یافت نشد"
        )
    if parent.parent_comment_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="پاسخ‌ها فقط یک سطح عمق دارند؛ نمی‌توان به یک پاسخ، پاسخ داد",
        )

    reply = EvaluationComment(
        evaluation_record_id=record.id,
        commenter_user_id=current_user.id,
        parent_comment_id=parent.id,
        stage=parent.stage,  # پاسخ در همان نخِ مرحلهٔ کامنتِ والد باقی می‌ماند
        comment_text=payload.comment_text,
    )
    db.add(reply)
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="comment_reply_added",
        evaluation_record_id=record.id,
        new_value={"parent_comment_id": parent.id, "stage": parent.stage.value},
    )
    # نویسندهٔ کامنتِ والد را از پاسخ باخبر می‌کنیم (اگر خودش پاسخ نداده باشد) تا
    # تأخیر اطلاع‌رسانی گفت‌وگوی برگشت کم شود.
    if parent.commenter_user_id != current_user.id:
        notify(
            db,
            [parent.commenter_user_id],
            type_="comment_reply_added",
            message=f"پاسخی به کامنت شما در پروندهٔ {record.evaluation_code} ثبت شد",
            evaluation_record_id=record.id,
            link=f"/evaluations/{record.id}",
        )
    db.commit()
    db.refresh(reply)
    return reply
