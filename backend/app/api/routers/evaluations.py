import secrets
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
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
from app.models.personnel import Personnel
from app.schemas.auth import CurrentUser
from app.schemas.evaluation import (
    CommentCreate,
    CommentRead,
    EvaluationCreate,
    EvaluationDetail,
    EvaluationPage,
    EvaluationRead,
    EvaluatorCommentUpdate,
    ReturnRequest,
    ScoresUpsert,
)
from app.services.audit import log_event
from app.services.documents import archive_final_pdf
from app.services.evaluation import next_evaluation_code
from app.services.excel import build_evaluations_workbook
from app.services.notifications import notify
from app.services.pdf import weasyprint_available
from app.services.snapshot import build_final_snapshot
from app.services.workflow import (
    active_indicators_by_id,
    apply_transition,
    finalize_scoring,
    is_manager_path,
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


def _ensure_can_view(record: EvaluationRecord, current_user: CurrentUser) -> None:
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


def _to_detail(db: Session, record: EvaluationRecord) -> EvaluationDetail:
    return EvaluationDetail.model_validate(record).model_copy(
        update={"was_returned": _was_returned(db, record.id)}
    )


def _replace_scores(db: Session, record: EvaluationRecord, payload: ScoresUpsert) -> list[dict]:
    indicators_by_id = active_indicators_by_id(db)
    indicator_ids_seen = set()
    rows = []
    for item in payload.scores:
        if item.indicator_id not in indicators_by_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"شاخص #{item.indicator_id} معتبر یا فعال نیست",
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
        require_roles(UserRole.unit_supervisor, UserRole.deputy)
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

    if personnel.is_manager:
        if current_user.role != UserRole.deputy or current_user.id != access.deputy_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="فقط معاونت مربوطه می‌تواند ارزیابی این فرد را آغاز کند",
            )
        # مسیر «مدیر»: معاونت خودش نمره‌دهنده اول است، پس پرونده مستقیماً در وضعیت
        # hr_approved (مرحله بررسی معاونت) ساخته می‌شود.
        record_status = EvaluationStatus.hr_approved
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
            current_user.role != UserRole.unit_supervisor
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
            EvaluationRecord.status != EvaluationStatus.finalized,
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

    record = EvaluationRecord(
        evaluation_code=next_evaluation_code(db),
        subject_personnel_id=personnel.id,
        unit_supervisor_user_id=unit_supervisor_user_id,
        deputy_user_id=access.deputy_user_id,
        ceo_user_id=access.ceo_user_id,
        period_id=open_period.id if open_period else None,
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
                EvaluationRecord.status != EvaluationStatus.finalized,
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
    if current_user.role == UserRole.unit_supervisor:
        query = query.where(EvaluationRecord.unit_supervisor_user_id == current_user.id)
    elif current_user.role == UserRole.deputy:
        query = query.where(EvaluationRecord.deputy_user_id == current_user.id)
    elif current_user.role == UserRole.ceo:
        query = query.where(EvaluationRecord.ceo_user_id == current_user.id)
    elif current_user.role == UserRole.employee:
        # کارمند فقط ارزیابی‌های نهایی‌شده خودش را می‌بیند (رابط اصلی‌اش /api/me است؛
        # این شاخه صریح مانع از افتادن نقش جدید در مسیر «HR همه را می‌بیند» است)
        if current_user.personnel_id is None:
            return EvaluationPage(total=0, items=[])
        query = query.where(
            EvaluationRecord.subject_personnel_id == current_user.personnel_id,
            EvaluationRecord.status == EvaluationStatus.finalized,
        )
    # hr می‌بیند همه را

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
    return _to_detail(db, record)


@router.put("/{evaluation_id}/scores", response_model=list[dict])
def upsert_scores(
    evaluation_id: int,
    payload: ScoresUpsert,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    record = _get_record_or_404(db, evaluation_id)

    is_supervisor_draft = (
        record.status == EvaluationStatus.draft
        and current_user.role == UserRole.unit_supervisor
        and current_user.id == record.unit_supervisor_user_id
    )
    is_manager_initial_scoring = (
        record.status == EvaluationStatus.hr_approved
        and is_manager_path(record)
        and current_user.role == UserRole.deputy
        and current_user.id == record.deputy_user_id
    )
    if not (is_supervisor_draft or is_manager_initial_scoring):
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
    db.commit()
    return rows


@router.patch("/{evaluation_id}/evaluator-comment", response_model=EvaluationRead)
def set_evaluator_comment(
    evaluation_id: int,
    payload: EvaluatorCommentUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EvaluationRead:
    record = _get_record_or_404(db, evaluation_id)
    # نمره‌دهنده اول این نظر را ثبت می‌کند: مسیر عادی مسئول واحد در draft است؛
    # مسیر «مدیر» معاونت خودش نمره‌دهندهٔ اول است و در hr_approved این کار را می‌کند.
    is_supervisor_draft = (
        current_user.role == UserRole.unit_supervisor
        and record.status == EvaluationStatus.draft
        and current_user.id == record.unit_supervisor_user_id
    )
    is_manager_initial_scoring = (
        current_user.role == UserRole.deputy
        and record.status == EvaluationStatus.hr_approved
        and is_manager_path(record)
        and current_user.id == record.deputy_user_id
    )
    if not (is_supervisor_draft or is_manager_initial_scoring):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="امکان ثبت نظر در این مرحله وجود ندارد"
        )
    record.evaluator_comment = payload.evaluator_comment
    db.commit()
    db.refresh(record)
    return _to_read(db, record)


@router.post("/{evaluation_id}/submit", response_model=EvaluationRead)
def submit_evaluation(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.unit_supervisor)),
) -> EvaluationRead:
    record = _get_record_or_404_for_update(db, evaluation_id)
    apply_transition(
        db, record, "submit", current_user,
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
    apply_transition(db, record, "hr_approve", current_user)
    db.commit()
    db.refresh(record)
    return _to_read(db, record)


@router.post("/{evaluation_id}/deputy-approve", response_model=EvaluationRead)
def deputy_approve(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.deputy)),
) -> EvaluationRead:
    record = _get_record_or_404_for_update(db, evaluation_id)

    def _before() -> None:
        # معاونت برای پرسنل «مدیر» نقش نمره‌دهنده اول را هم بازی می‌کند
        if is_manager_path(record):
            finalize_scoring(db, record, current_user)

    apply_transition(db, record, "deputy_approve", current_user, before=_before)
    db.commit()
    db.refresh(record)
    return _to_read(db, record)


@router.post("/{evaluation_id}/ceo-finalize", response_model=EvaluationRead)
def ceo_finalize(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.ceo)),
) -> EvaluationRead:
    record = _get_record_or_404_for_update(db, evaluation_id)

    def _before() -> None:
        record.finalized_at = datetime.now(UTC)
        record.final_snapshot = build_final_snapshot(db, record)
        # توکن تصادفی صفحهٔ تأیید عمومی؛ evaluation_code ترتیبی است و نباید کلید
        # جست‌وجوی یک endpoint بدون احراز هویت باشد (قابل شمارش/enumeration)
        record.verify_token = secrets.token_urlsafe(24)

    apply_transition(db, record, "ceo_finalize", current_user, before=_before)
    # سند PDF نهایی همین‌جا یک‌بار تولید، هش و آرشیو می‌شود تا از این پس همان بایت‌ها
    # سرو شوند (سند حقوقی byte-stable) و QR تأیید اصالت داشته باشد.
    db.flush()
    archive_final_pdf(db, record)
    db.commit()
    db.refresh(record)
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


@router.get("/{evaluation_id}/summary.pdf")
def evaluation_summary_pdf(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    record = _get_record_or_404(db, evaluation_id)
    _ensure_can_view(record, current_user)
    # خروجی PDF فقط برای منابع انسانی — سایر نقش‌ها حتی اگر پرونده را ببینند، اجازهٔ
    # چاپ/دانلود سند رسمی را ندارند.
    if current_user.role != UserRole.hr:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="خروجی PDF فقط برای منابع انسانی در دسترس است",
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
