import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.enums import CommentStage, EvaluationStatus, PeriodStatus, UserRole
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


def _ensure_can_view(record: EvaluationRecord, current_user: CurrentUser) -> None:
    if current_user.role == UserRole.hr:
        return
    allowed_ids = {record.unit_supervisor_user_id, record.deputy_user_id, record.ceo_user_id}
    if current_user.id not in allowed_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="شما به این ارزیابی دسترسی ندارید"
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
        # دو درخواست هم‌زمان: ایندکس یکتای جزئی برنده را مشخص می‌کند
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "برای این پرسنل یک ارزیابی باز (نهایی‌نشده) وجود دارد؛ ابتدا همان پرونده را تکمیل کنید."},
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


@router.get("", response_model=EvaluationPage)
def list_evaluations(
    q: str | None = None,
    status_filter: EvaluationStatus | None = Query(default=None, alias="status"),
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

    if status_filter is not None:
        query = query.where(EvaluationRecord.status == status_filter)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.join(
            Personnel, Personnel.id == EvaluationRecord.subject_personnel_id
        ).where(
            EvaluationRecord.evaluation_code.ilike(pattern)
            | Personnel.full_name.ilike(pattern)
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
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> Response:
    """خروجی Excel از کل ارزیابی‌ها (فقط HR) برای گزارش‌گیری بیرون از سامانه."""
    records = db.scalars(
        select(EvaluationRecord).order_by(EvaluationRecord.created_at.desc())
    ).all()
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
) -> EvaluationRecord:
    record = _get_record_or_404(db, evaluation_id)
    _ensure_can_view(record, current_user)
    return record


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
) -> EvaluationRecord:
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
    return record


@router.post("/{evaluation_id}/submit", response_model=EvaluationRead)
def submit_evaluation(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.unit_supervisor)),
) -> EvaluationRecord:
    record = _get_record_or_404(db, evaluation_id)
    apply_transition(
        db, record, "submit", current_user,
        before=lambda: finalize_scoring(db, record, current_user),
    )
    db.commit()
    db.refresh(record)
    return record


@router.post("/{evaluation_id}/hr-approve", response_model=EvaluationRead)
def hr_approve(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> EvaluationRecord:
    record = _get_record_or_404(db, evaluation_id)
    apply_transition(db, record, "hr_approve", current_user)
    db.commit()
    db.refresh(record)
    return record


@router.post("/{evaluation_id}/deputy-approve", response_model=EvaluationRead)
def deputy_approve(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.deputy)),
) -> EvaluationRecord:
    record = _get_record_or_404(db, evaluation_id)

    def _before() -> None:
        # معاونت برای پرسنل «مدیر» نقش نمره‌دهنده اول را هم بازی می‌کند
        if is_manager_path(record):
            finalize_scoring(db, record, current_user)

    apply_transition(db, record, "deputy_approve", current_user, before=_before)
    db.commit()
    db.refresh(record)
    return record


@router.post("/{evaluation_id}/ceo-finalize", response_model=EvaluationRead)
def ceo_finalize(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.ceo)),
) -> EvaluationRecord:
    record = _get_record_or_404(db, evaluation_id)

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
    return record


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
) -> EvaluationRecord:
    """برگشت پرونده یک مرحله به عقب با ذکر دلیل اجباری؛ امتیازهای قبلی حفظ می‌شوند."""
    record = _get_record_or_404(db, evaluation_id)
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
    return record


@router.get("/{evaluation_id}/summary.pdf")
def evaluation_summary_pdf(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    record = _get_record_or_404(db, evaluation_id)
    _ensure_can_view(record, current_user)
    if record.status != EvaluationStatus.finalized or record.final_snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="ارزیابی هنوز نهایی نشده است"
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
