"""ابزارهای پروندهٔ ارزیابی: جست‌وجو، جزئیات، آغاز، گذارِ گردش‌کار، دیدگاه، خودارزیابی.

قاعدهٔ قرارداد با رابط:
* دامنهٔ دید ارزیابی‌ها از `scope_evaluations_for_role` می‌آید — همان تابعی
  که فهرستِ رابط استفاده می‌کند، پس دستیار هیچ پنجرهٔ دیده‌بانیِ اضافه‌ای
  باز نمی‌کند.
* هر گذار وضعیت از `workflow.apply_transition` می‌گذرد؛ گاردِ نقش و مرحله و
  «تصمیم دربارهٔ خود» همان است که دکمه‌های رابط می‌بینند.
* ثبت امتیاز عمداً ابزار ندارد: نمره‌دهی یعنی وزن و شواهد و قانونِ نسخه؛
  یک جملهٔ چت آن را نیمه‌کاره می‌سازد. دستیار پرونده را می‌خواند، پیش
  می‌برد و توضیح می‌دهد — امتیاز را فرم ثبت می‌کند.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Capability, CommentStage, EvaluationStatus, UserRole
from app.models.evaluation import EvaluationComment, EvaluationRecord
from app.models.personnel import Personnel
from app.services.ai.tools.base import ToolContext, ToolOutcome, json_content, tool
from app.services.workflow import apply_transition

_STATUS_LABELS = {
    "draft": "نمره‌دهی",
    "submitted": "بررسی منابع انسانی",
    "hr_approved": "بررسی معاونت",
    "deputy_approved": "تأیید نهایی مدیرعامل",
    "finalized": "نهایی‌شده",
    "cancelled": "لغوشده",
}


def _record_or_404(db: Session, evaluation_id: int) -> EvaluationRecord:
    record = db.get(EvaluationRecord, int(evaluation_id))
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پروندهٔ ارزیابی پیدا نشد")
    return record


def _subject_name(db: Session, record: EvaluationRecord) -> str:
    person = db.get(Personnel, record.subject_personnel_id)
    return person.full_name if person else "?"


def _describe_record(db: Session, record: EvaluationRecord) -> dict:
    return {
        "id": record.id,
        "evaluation_code": record.evaluation_code,
        "subject_personnel_id": record.subject_personnel_id,
        "status": record.status.value,
        "status_label": _STATUS_LABELS.get(record.status.value, record.status.value),
        "final_weighted_pct": float(record.final_weighted_pct) if record.final_weighted_pct is not None else None,
        "recommendation": record.recommendation,
    }


@tool(
    name="search_evaluations",
    description="جست‌وجوی پرونده‌های ارزیابی در دامنهٔ دسترسی خودتان (بسته به نقش). می‌توانید بر وضعیت، واحد، کد پرونده یا نام فرد فیلتر کنید.",
    category="ارزیابی",
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "q": {"type": "string", "description": "بخشی از کد پرونده یا نام فرد"},
            "status": {"type": "string", "enum": [s.value for s in EvaluationStatus]},
            "subject_personnel_id": {"type": "integer"},
            "limit": {"type": "integer"},
        },
    },
)
def search_evaluations(
    ctx: ToolContext, q: str = "", status: str = "", subject_personnel_id: int | None = None, limit: int = 15
) -> ToolOutcome:
    from app.api.routers.evaluations import _apply_evaluation_filters, scope_evaluations_for_role

    db = ctx.db
    query = select(EvaluationRecord)
    query = scope_evaluations_for_role(query, ctx.user)
    status_filter = EvaluationStatus(status) if status else None
    query = _apply_evaluation_filters(
        query,
        q=q or None,
        status_filter=status_filter,
        org_unit=None,
        created_from=None,
        created_to=None,
        min_final_pct=None,
        max_final_pct=None,
        subject_personnel_id=subject_personnel_id,
    )
    records = list(db.scalars(query.order_by(EvaluationRecord.created_at.desc()).limit(max(1, min(int(limit or 15), 50)))))
    items = []
    for record in records:
        item = _describe_record(db, record)
        item["subject_name"] = _subject_name(db, record)
        items.append(item)
    return ToolOutcome(
        content=json_content({"matches": len(items), "evaluations": items}),
        ui={"kind": "evaluation_list", "items": items},
        summary=f"جست‌وجوی پرونده‌ها ({len(items)} نتیجه)",
    )


def _describe_search_evaluations(q="", status="", **_):
    bits = []
    if q:
        bits.append(f"«{q}»")
    if status:
        bits.append(f"وضعیت {status}")
    return "جست‌وجوی پرونده‌ها" + (" " + " ".join(bits) if bits else "")


search_evaluations.describe = _describe_search_evaluations


@tool(
    name="get_evaluation",
    description="نمای کامل یک پرونده: مرحلهٔ گردش‌کار، امتیاز شاخص‌ها، نتیجهٔ نهایی، دیدگاه‌ها و خودارزیابی (در حد دسترسی نقش شما).",
    category="ارزیابی",
    read_only=True,
    parameters={"type": "object", "properties": {"evaluation_id": {"type": "integer"}}, "required": ["evaluation_id"]},
)
def get_evaluation(ctx: ToolContext, evaluation_id: int) -> ToolOutcome:
    db = ctx.db
    record = _record_or_404(db, evaluation_id)
    # همان گاردِ GET تکیِ رابط: خودِ موضوع پرونده نمی‌بیند؛ زنجیره و منابع انسانی می‌بینند.
    from app.api.routers.evaluations import _ensure_can_view, _to_detail

    _ensure_can_view(record, ctx.user)
    detail = _to_detail(db, record, ctx.user)
    payload = detail.model_dump(mode="json")
    # نثرِ مدل باید خوانا بماند؛ بدنه‌های سنگین رابط را کوتاه می‌کنیم.
    payload.pop("final_snapshot", None)
    return ToolOutcome(
        content=json_content(payload),
        ui={"kind": "evaluation_card", "evaluation": _describe_record(db, record)},
        summary=f"جزئیات پروندهٔ {record.evaluation_code} ({_subject_name(db, record)})",
    )


@tool(
    name="create_evaluation",
    description="آغاز پروندهٔ ارزیابی برای یک پرسنل. فقط مسئول واحدِ همان فرد (یا معاونت، برای پرسنلِ نشانِ «مدیر») می‌تواند آغاز کند؛ پرسنل باید فعال و دارای زنجیره باشد.",
    category="ارزیابی",
    risky=True,
    parameters={"type": "object", "properties": {"personnel_id": {"type": "integer"}}, "required": ["personnel_id"]},
)
def create_evaluation(ctx: ToolContext, personnel_id: int) -> ToolOutcome:
    from app.api.routers.evaluations import create_evaluation as create_endpoint
    from app.schemas.evaluation import EvaluationCreate

    record = create_endpoint(
        payload=EvaluationCreate(subject_personnel_id=int(personnel_id)),
        db=ctx.db,
        current_user=ctx.user,
    )
    return ToolOutcome(
        content=json_content({
            "created": True,
            "evaluation": _describe_record(ctx.db, record),
            "subject_name": _subject_name(ctx.db, record),
            "note": "پرونده در مرحلهٔ نمره‌دهی است؛ ثبت امتیاز از فرم نمره‌دهی انجام می‌شود.",
        }),
        summary=f"پروندهٔ ارزیابی {_subject_name(ctx.db, record)} آغاز شد ({record.evaluation_code})",
    )


@tool(
    name="advance_evaluation",
    description="پیش‌بردن پرونده در زنجیرهٔ تأیید: submit (ارسال از نمره‌دهی)، hr_approve، deputy_approve، ceo_finalize، return (برگشت با دلیل الزامی)، cancel (لغو با دلیل، منابع انسانی)، hr_claim (تحویل‌گرفتن). مجوز هر گذار را ماشین حالت سامانه می‌سنجد.",
    category="ارزیابی",
    risky=True,
    parameters={
        "type": "object",
        "properties": {
            "evaluation_id": {"type": "integer"},
            "action": {
                "type": "string",
                "enum": ["submit", "hr_approve", "deputy_approve", "ceo_finalize", "return", "cancel", "hr_claim"],
            },
            "reason": {"type": "string", "description": "برای return و cancel الزامی"},
        },
        "required": ["evaluation_id", "action"],
    },
)
def advance_evaluation(ctx: ToolContext, evaluation_id: int, action: str, reason: str = "") -> ToolOutcome:
    db = ctx.db
    record = _record_or_404(db, evaluation_id)
    action = action.strip()
    if action in ("return", "cancel") and not (reason or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "برای برگشت یا لغو، ذکر دلیل الزامی است")

    from app.api.routers.evaluations import _get_record_or_404_for_update

    # همان قفل ردیفی که گذارهای رابط دارند؛ دوبار کلیک یا دو درخواستِ هم‌زمان
    # از مسیر دستیار هم باید تمیز رد شود.
    record = _get_record_or_404_for_update(db, evaluation_id)
    before_status = record.status.value
    apply_transition(db, record, action, ctx.user)
    db.commit()
    db.refresh(record)
    subject = _subject_name(db, record)
    return ToolOutcome(
        content=json_content({
            "advanced": True,
            "action": action,
            "evaluation": _describe_record(db, record),
            "subject_name": subject,
            "previous_status": before_status,
        }),
        summary=f"پروندهٔ {record.evaluation_code} ({subject}) از «{_STATUS_LABELS.get(before_status, before_status)}» به «{_STATUS_LABELS.get(record.status.value)}» رفت",
    )


def _describe_advance(evaluation_id, action, reason="", **_):
    return f"گذار «{action}» روی پروندهٔ #{evaluation_id}" + (f" با دلیل «{reason}»" if reason else "")


advance_evaluation.describe = _describe_advance


@tool(
    name="add_evaluation_comment",
    description="ثبت دیدگاه روی پروندهٔ ارزیابی (پاسخِ رشته‌ای با parent_comment_id). فقط اعضای زنجیره و منابع انسانی.",
    category="ارزیابی",
    risky=False,
    read_only=False,
    parameters={
        "type": "object",
        "properties": {
            "evaluation_id": {"type": "integer"},
            "comment_text": {"type": "string"},
            "parent_comment_id": {"type": "integer", "description": "برای پاسخ به یک دیدگاه"},
        },
        "required": ["evaluation_id", "comment_text"],
    },
)
def add_evaluation_comment(
    ctx: ToolContext, evaluation_id: int, comment_text: str, parent_comment_id: int | None = None
) -> ToolOutcome:
    db = ctx.db
    record = _record_or_404(db, evaluation_id)
    from app.api.routers.evaluations import _ensure_can_view

    _ensure_can_view(record, ctx.user)
    text = (comment_text or "").strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "متن دیدگاه خالی است")

    stage_map = {
        UserRole.hr: CommentStage.hr_review,
        UserRole.unit_supervisor: CommentStage.hr_review,
        UserRole.deputy: CommentStage.deputy_review,
        UserRole.ceo: CommentStage.ceo_final,
    }
    stage = stage_map.get(ctx.user.role, CommentStage.hr_review)
    if record.status is EvaluationStatus.finalized:
        stage = CommentStage.ceo_final
    parent = None
    if parent_comment_id:
        parent = db.get(EvaluationComment, int(parent_comment_id))
        if parent is None or parent.evaluation_record_id != record.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "دیدگاهِ مبدأ در همین پرونده نیست")

    comment = EvaluationComment(
        evaluation_record_id=record.id,
        commenter_user_id=ctx.user.id,
        parent_comment_id=parent.id if parent else None,
        stage=stage,
        comment_text=text[:4000],
    )
    db.add(comment)
    db.flush()

    from app.services.audit import log_event

    log_event(
        db,
        actor_user_id=ctx.user.id,
        event_type="comment_added",
        evaluation_record_id=record.id,
        new_value={"comment_id": comment.id, "via": "ai_copilot"},
    )
    db.commit()
    return ToolOutcome(
        content=json_content({"comment_id": comment.id, "evaluation_code": record.evaluation_code}),
        summary=f"دیدگاه روی پروندهٔ {record.evaluation_code} ثبت شد",
    )


@tool(
    name="invite_self_assessment",
    description="فرستادن دعوت‌نامهٔ خودارزیابی به یک پرسنل (منابع انسانی). پروندهٔ باز لازم دارد.",
    category="ارزیابی",
    risky=True,
    capabilities=(Capability.manage_personnel,),
    roles=(UserRole.hr,),
    parameters={"type": "object", "properties": {"personnel_id": {"type": "integer"}}, "required": ["personnel_id"]},
)
def invite_self_assessment(ctx: ToolContext, personnel_id: int) -> ToolOutcome:
    from app.services.self_assessment import invite

    db = ctx.db
    person = db.get(Personnel, int(personnel_id))
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پرسنلی با این شناسه پیدا نشد")
    record = invite(db, person, ctx.user.id)
    db.commit()
    return ToolOutcome(
        content=json_content({
            "invited": True,
            "personnel_id": person.id,
            "evaluation_code": record.evaluation_code if record else None,
        }),
        summary=f"دعوت خودارزیابی برای «{person.full_name}» فرستاده شد",
    )


@tool(
    name="my_open_cases",
    description="پرونده‌های بازِ روی میزِ خودتان بسته به نقش: نمره‌دهیِ در جریان، صف بررسی منابع انسانی، تأیید معاونت، تأیید نهایی.",
    category="ارزیابی",
    read_only=True,
    parameters={"type": "object", "properties": {"limit": {"type": "integer"}}},
)
def my_open_cases(ctx: ToolContext, limit: int = 15) -> ToolOutcome:
    db = ctx.db
    role = ctx.user.role
    if role == UserRole.unit_supervisor:
        stage_condition = (EvaluationRecord.status == EvaluationStatus.draft) & (
            EvaluationRecord.unit_supervisor_user_id == ctx.user.id
        )
    elif role == UserRole.hr:
        stage_condition = EvaluationRecord.status == EvaluationStatus.submitted
    elif role == UserRole.deputy:
        stage_condition = (
            (EvaluationRecord.status == EvaluationStatus.hr_approved)
            | ((EvaluationRecord.status == EvaluationStatus.draft) & (EvaluationRecord.deputy_user_id == ctx.user.id))
        )
    elif role == UserRole.ceo:
        stage_condition = EvaluationRecord.status == EvaluationStatus.deputy_approved
    elif role == UserRole.employee:
        stage_condition = EvaluationRecord.status == EvaluationStatus.finalized
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "این نقش به پرونده‌های ارزیابی دسترسی ندارد")

    stmt = select(EvaluationRecord).where(stage_condition).order_by(EvaluationRecord.stage_entered_at).limit(max(1, min(int(limit or 15), 50)))
    records = list(db.scalars(stmt))
    items = []
    for record in records:
        item = _describe_record(db, record)
        item["subject_name"] = _subject_name(db, record)
        item["stage_entered_at"] = record.stage_entered_at.isoformat() if record.stage_entered_at else None
        items.append(item)
    return ToolOutcome(
        content=json_content({"count": len(items), "cases": items}),
        ui={"kind": "evaluation_list", "items": items},
        summary=f"پرونده‌های بازِ روی میز شما ({len(items)} پرونده)",
    )


@tool(
    name="explain_evaluation_rules",
    description="خواندن طرح نمره‌دهیِ مؤثر یک پرونده (یا طرح فعال): وزن بخش‌ها، آستانه‌های برچسب، قانون شواهد، سقف امتیاز ویژه — به زبان ساده.",
    category="ارزیابی",
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "evaluation_id": {"type": "integer", "description": "پروندهٔ مقصد؛ اگر خالی باشد طرح فعال می‌آید"},
        },
    },
)
def explain_evaluation_rules(ctx: ToolContext, evaluation_id: int | None = None) -> ToolOutcome:
    db = ctx.db
    from app.models.scoring_scheme import ScoringScheme
    from app.services.scoring_scheme import active_scheme

    scheme = None
    if evaluation_id:
        record = _record_or_404(db, evaluation_id)
        if record.scoring_scheme_id is not None:
            scheme = db.get(ScoringScheme, record.scoring_scheme_id)
        else:
            scheme = active_scheme(db)
    else:
        scheme = active_scheme(db)
    if scheme is None:
        return ToolOutcome(content=json_content({"note": "طرحی ثبت نشده؛ قواعد پیش‌فرض قدیمی اعمال می‌شود."}), summary="قواعد نمره‌دهی")
    payload = {
        "version": scheme.version,
        "name": scheme.name,
        "status": scheme.status.value,
        "general_section_weight": float(scheme.general_section_weight),
        "specialized_section_weight": float(scheme.specialized_section_weight),
        "evidence_required_scores": scheme.evidence_required_scores,
        "evidence_min_words": scheme.evidence_min_words,
        "evidence_max_words": scheme.evidence_max_words,
        "bonus_max_points": float(scheme.bonus_max_points),
        "improvement_plan_max_pct": float(scheme.improvement_plan_max_pct),
        "thresholds": scheme.thresholds,
        "indicator_weights": {str(k): float(v) for k, v in (scheme.indicator_weights or {}).items()},
    }
    return ToolOutcome(
        content=json_content(payload),
        summary=f"قواعد طرح نمره‌دهی نسخهٔ {scheme.version}",
    )
