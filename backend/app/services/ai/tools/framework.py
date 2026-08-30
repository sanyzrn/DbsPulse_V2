"""ابزارهای چارچوب ارزیابی: شاخص‌ها، طرح نمره‌دهی، دوره‌ها، آغاز گروهی، برنامه‌های بهبود.

نسخه‌پذیری خطِ قرمز این سامانه است: هر تغییرِ شاخص یا طرح از همان سرویس‌های
نسخه‌دار می‌گذرد تا معنای ارزیابی‌های گذشته بی‌صدا عوض نشود. «اثر پیش از
ثبت» هم ابزارِ مستقل دارد، چون تصمیمِ درست لازمش دارد نه حدسِ بعد از ثبت را.
"""
from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select

from app.models.enums import Capability, UserRole
from app.services.ai.tools.base import ToolContext, ToolOutcome, json_content, tool

# ── شاخص‌ها ────────────────────────────────────────────────────────────────


@tool(
    name="list_indicators",
    description="فهرست شاخص‌های ارزیابی با بخش، دسته و فعال/غیرفعال بودن.",
    category="چارچوب",
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "section": {"type": "string", "enum": ["general", "specialized"]},
            "include_inactive": {"type": "boolean"},
        },
    },
)
def list_indicators(ctx: ToolContext, section: str = "", include_inactive: bool = False) -> ToolOutcome:
    from app.models.enums import IndicatorSection
    from app.models.indicator import Indicator

    db = ctx.db
    stmt = select(Indicator)
    if section:
        stmt = stmt.where(Indicator.section == IndicatorSection(section))
    if not include_inactive:
        stmt = stmt.where(Indicator.is_active.is_(True))
    stmt = stmt.order_by(Indicator.section, Indicator.display_order, Indicator.id)
    rows = list(db.scalars(stmt))
    items = [
        {
            "id": i.id,
            "section": i.section.value,
            "section_label": "عمومی" if i.section.value == "general" else "تخصصی",
            "category": i.category,
            "description": i.description,
            "is_active": i.is_active,
            "display_order": i.display_order,
        }
        for i in rows
    ]
    return ToolOutcome(
        content=json_content({"count": len(items), "indicators": items}),
        ui={"kind": "indicator_list", "items": items},
        summary=f"فهرست شاخص‌ها ({len(items)} شاخص)",
    )


@tool(
    name="create_indicator",
    description="افزودن شاخص تازه به انتهای بخش خودش. تا در چارچوبِ تازه‌ای ثبت نشود روی پرونده‌های در جریان اثری ندارد.",
    category="چارچوب",
    risky=True,
    capabilities=(Capability.manage_scoring,),
    parameters={
        "type": "object",
        "properties": {
            "section": {"type": "string", "enum": ["general", "specialized"]},
            "category": {"type": "string"},
            "description": {"type": "string"},
        },
        "required": ["section", "category", "description"],
    },
)
def create_indicator(ctx: ToolContext, section: str, category: str, description: str) -> ToolOutcome:
    from app.models.enums import IndicatorSection
    from app.models.indicator import Indicator
    from app.services.audit import log_event

    db = ctx.db
    text = (description or "").strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "متن شاخص خالی است")
    indicator = Indicator(
        section=IndicatorSection(section.strip()),
        category=(category or "").strip()[:150],
        description=text[:1000],
        display_order=0,
        is_active=True,
    )
    db.add(indicator)
    db.flush()
    log_event(
        db,
        actor_user_id=ctx.user.id,
        event_type="indicator_created",
        new_value={"id": indicator.id, "section": section, "category": category, "via": "ai_copilot"},
    )
    db.commit()
    return ToolOutcome(
        content=json_content({"created": True, "indicator": {"id": indicator.id, "description": indicator.description}}),
        summary=f"شاخص «{indicator.category}» افزوده شد",
    )


def _describe_create_indicator(category, section="", **_):
    return f"افزودن شاخص «{category}»" + (f" در بخش {section}" if section else "")


create_indicator.describe = _describe_create_indicator


@tool(
    name="update_indicator",
    description="ویرایش متن یا دستهٔ شاخص، یا غیرفعال‌کردنش. تغییرِ معنایی شاخصِ استفاده‌شده باید به «جایگزینی» برسد؛ این‌جا ویرایشِ نگارشی است.",
    category="چارچوب",
    risky=True,
    capabilities=(Capability.manage_scoring,),
    parameters={
        "type": "object",
        "properties": {
            "indicator_id": {"type": "integer"},
            "description": {"type": "string"},
            "category": {"type": "string"},
            "is_active": {"type": "boolean"},
        },
        "required": ["indicator_id"],
    },
)
def update_indicator(
    ctx: ToolContext,
    indicator_id: int,
    description: str | None = None,
    category: str | None = None,
    is_active: bool | None = None,
) -> ToolOutcome:
    from app.models.indicator import Indicator
    from app.services.audit import log_event

    db = ctx.db
    indicator = db.get(Indicator, int(indicator_id))
    if indicator is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "شاخصی با این شناسه پیدا نشد")
    before = {"description": indicator.description, "category": indicator.category, "is_active": indicator.is_active}
    changed = {}
    if description is not None and description.strip():
        indicator.description = description.strip()[:1000]
        changed["description"] = indicator.description
    if category is not None and category.strip():
        indicator.category = category.strip()[:150]
        changed["category"] = indicator.category
    if is_active is not None:
        indicator.is_active = bool(is_active)
        changed["is_active"] = indicator.is_active
    if not changed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تغییری داده نشده است")
    log_event(
        db,
        actor_user_id=ctx.user.id,
        event_type="indicator_updated",
        old_value={"id": indicator.id, **{k: str(v) for k, v in before.items()}},
        new_value={"id": indicator.id, "via": "ai_copilot", **{k: str(v) for k, v in changed.items()}},
    )
    db.commit()
    return ToolOutcome(
        content=json_content({"updated": True, "indicator_id": indicator.id}),
        summary=f"شاخص «{indicator.category}» به‌روز شد",
    )


# ── طرح نمره‌دهی ───────────────────────────────────────────────────────────


@tool(
    name="list_scoring_schemes",
    description="همهٔ نسخه‌های طرح نمره‌دهی از تازه به قدیم، با وضعیت پیش‌نویس/فعال/بازنشسته.",
    category="چارچوب",
    read_only=True,
    capabilities=(Capability.manage_scoring,),
    parameters={"type": "object", "properties": {}},
)
def list_scoring_schemes(ctx: ToolContext) -> ToolOutcome:
    from app.models.scoring_scheme import ScoringScheme

    db = ctx.db
    rows = list(db.scalars(select(ScoringScheme).order_by(ScoringScheme.version.desc())))
    items = [
        {
            "id": s.id,
            "version": s.version,
            "name": s.name,
            "status": s.status.value,
            "general_section_weight": float(s.general_section_weight),
            "specialized_section_weight": float(s.specialized_section_weight),
            "bonus_max_points": float(s.bonus_max_points),
            "improvement_plan_max_pct": float(s.improvement_plan_max_pct),
            "activated_at": s.activated_at.isoformat() if s.activated_at else None,
        }
        for s in rows
    ]
    return ToolOutcome(
        content=json_content({"count": len(items), "schemes": items}),
        summary=f"نسخه‌های طرح نمره‌دهی ({len(items)})",
    )


@tool(
    name="create_scoring_scheme_draft",
    description="ساخت پیش‌نویس تازهٔ طرح نمره‌دهی. فعال‌سازی گامِ جداگانه‌ای است که سازنده نمی‌تواند خودش انجام دهد.",
    category="چارچوب",
    risky=True,
    capabilities=(Capability.manage_scoring,),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "general_section_weight": {"type": "number", "description": "۰ تا ۱؛ جمع دو وزن باید ۱ شود"},
            "specialized_section_weight": {"type": "number"},
            "evidence_min_words": {"type": "integer"},
            "evidence_max_words": {"type": "integer"},
            "bonus_max_points": {"type": "number"},
            "improvement_plan_max_pct": {"type": "number"},
        },
        "required": ["name"],
    },
)
def create_scoring_scheme_draft(
    ctx: ToolContext,
    name: str,
    general_section_weight: float | None = None,
    specialized_section_weight: float | None = None,
    evidence_min_words: int | None = None,
    evidence_max_words: int | None = None,
    bonus_max_points: float | None = None,
    improvement_plan_max_pct: float | None = None,
) -> ToolOutcome:
    from app.models.scoring_scheme import ScoringScheme
    from app.services.audit import log_event
    from app.services.scoring_scheme import next_version

    db = ctx.db
    scheme = ScoringScheme(
        version=next_version(db),
        name=(name or "").strip()[:200] or f"طرح نسخهٔ {db.scalar(select(func.max(ScoringScheme.version)))}",
        status="draft",
        general_section_weight=general_section_weight if general_section_weight is not None else 0.6,
        specialized_section_weight=specialized_section_weight if specialized_section_weight is not None else 0.4,
        evidence_required_scores=[1, 5],
        evidence_min_words=evidence_min_words if evidence_min_words is not None else 3,
        evidence_max_words=evidence_max_words if evidence_max_words is not None else 40,
        bonus_max_points=bonus_max_points if bonus_max_points is not None else 5.0,
        improvement_plan_max_pct=improvement_plan_max_pct if improvement_plan_max_pct is not None else 75.0,
        thresholds=[
            {"upper_exclusive": 60, "label": "عدم تمدید"},
            {"upper_exclusive": 75, "label": "تمدید مشروط"},
            {"upper_exclusive": 90, "label": "تمدید"},
            {"upper_exclusive": 101, "label": "تمدیـد ممتاز"},
        ],
        indicator_weights={},
        created_by_user_id=ctx.user.id,
    )
    db.add(scheme)
    db.flush()
    log_event(
        db,
        actor_user_id=ctx.user.id,
        event_type="scoring_scheme_created",
        new_value={"id": scheme.id, "version": scheme.version, "via": "ai_copilot"},
    )
    db.commit()
    return ToolOutcome(
        content=json_content({"created": True, "scheme": {"id": scheme.id, "version": scheme.version, "name": scheme.name}}),
        summary=f"پیش‌نویس طرح نمره‌دهی نسخهٔ {scheme.version} ساخته شد",
    )


@tool(
    name="activate_scoring_scheme",
    description="فعال‌کردن نسخهٔ طرح نمره‌دهی. دو نفره است: سازنده نمی‌تواند خودش فعالش کند. اثرش روی پرونده‌های آینده است، نه گذشته.",
    category="چارچوب",
    risky=True,
    capabilities=(Capability.manage_scoring,),
    parameters={"type": "object", "properties": {"scheme_id": {"type": "integer"}}, "required": ["scheme_id"]},
)
def activate_scoring_scheme(ctx: ToolContext, scheme_id: int) -> ToolOutcome:
    from app.models.scoring_scheme import ScoringScheme
    from app.services.audit import log_event
    from app.services.scoring_scheme import activate

    db = ctx.db
    scheme = db.get(ScoringScheme, int(scheme_id))
    if scheme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "طرحی با این شناسه پیدا نشد")
    activate(db, scheme, actor_user_id=ctx.user.id)
    log_event(
        db,
        actor_user_id=ctx.user.id,
        event_type="scoring_scheme_activated",
        new_value={"id": scheme.id, "version": scheme.version, "via": "ai_copilot"},
    )
    db.commit()
    return ToolOutcome(
        content=json_content({"activated": True, "version": scheme.version, "name": scheme.name}),
        summary=f"طرح نمره‌دهی نسخهٔ {scheme.version} فعال شد",
    )


# ── دوره‌ها و آغاز گروهی ───────────────────────────────────────────────────


@tool(
    name="list_periods",
    description="دوره‌های ارزیابی با وضعیت باز/بسته.",
    category="دوره‌ها",
    read_only=True,
    roles=(UserRole.hr,),
    parameters={"type": "object", "properties": {}},
)
def list_periods(ctx: ToolContext) -> ToolOutcome:
    from app.models.evaluation_period import EvaluationPeriod

    db = ctx.db
    rows = list(db.scalars(select(EvaluationPeriod).order_by(EvaluationPeriod.starts_on.desc())))
    items = [
        {
            "id": p.id,
            "name": p.name,
            "starts_on": p.starts_on.isoformat(),
            "ends_on": p.ends_on.isoformat(),
            "status": p.status.value,
        }
        for p in rows
    ]
    return ToolOutcome(content=json_content({"periods": items}), summary=f"دوره‌های ارزیابی ({len(items)})")


@tool(
    name="create_period",
    description="ساخت دورهٔ ارزیابی تازه (منابع انسانی).",
    category="دوره‌ها",
    risky=True,
    roles=(UserRole.hr,),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "starts_on": {"type": "string"},
            "ends_on": {"type": "string"},
        },
        "required": ["name", "starts_on", "ends_on"],
    },
)
def create_period(ctx: ToolContext, name: str, starts_on: str, ends_on: str) -> ToolOutcome:
    from app.api.routers.periods import create_period as create_endpoint
    from app.schemas.period import PeriodCreate

    period = create_endpoint(
        payload=PeriodCreate(name=name, starts_on=_parse_date(starts_on), ends_on=_parse_date(ends_on)),
        db=ctx.db,
        current_user=ctx.user,
    )
    return ToolOutcome(
        content=json_content({"created": True, "period": {"id": period.id, "name": period.name}}),
        summary=f"دورهٔ «{period.name}» ساخته شد",
    )


@tool(
    name="period_progress",
    description="پیشرفت یک دوره: چند پرونده نهایی شده، چند در جریان است، چه کسانی هنوز بدون پرونده‌اند.",
    category="دوره‌ها",
    read_only=True,
    roles=(UserRole.hr,),
    parameters={"type": "object", "properties": {"period_id": {"type": "integer"}}, "required": ["period_id"]},
)
def period_progress(ctx: ToolContext, period_id: int) -> ToolOutcome:
    db = ctx.db
    from app.api.routers.periods import _get_period_or_404
    from app.api.routers.periods import period_progress as progress_endpoint

    period = _get_period_or_404(db, int(period_id))
    progress = progress_endpoint(period_id=period.id, db=db, current_user=ctx.user)
    payload = progress.model_dump(mode="json")
    return ToolOutcome(
        content=json_content(payload),
        summary=f"پیشرفت دورهٔ «{period.name}»: {payload.get('finalized', 0)} نهایی از {payload.get('eligible', 0)}",
    )


@tool(
    name="preview_bulk_evaluations",
    description="آزمایشِ اجرای گروهی ارزیابی برای یک گروه (بدون ثبت): چه کسانی پرونده می‌گیرند، چه کسانی بلاک‌اند و چرا.",
    category="دوره‌ها",
    read_only=True,
    roles=(UserRole.hr,),
    parameters={
        "type": "object",
        "properties": {
            "org_unit": {"type": "string"},
            "only_managers": {"type": "boolean"},
            "contract_ends_before": {"type": "string"},
        },
    },
)
def preview_bulk_evaluations(
    ctx: ToolContext, org_unit: str = "", only_managers: bool = False, contract_ends_before: str = ""
) -> ToolOutcome:
    from app.services.bulk_evaluation import CohortFilter, plan, summarise

    db = ctx.db
    cohort = CohortFilter(
        org_unit=(org_unit or "").strip() or None,
        only_managers=bool(only_managers),
        contract_ends_before=_parse_date(contract_ends_before),
    )
    plans = plan(db, cohort)
    items = [
        {
            "personnel_id": p.personnel_id,
            "full_name": p.full_name,
            "org_unit": p.org_unit,
            "outcome": p.outcome.value,
            "reason": p.reason,
        }
        for p in plans
    ]
    return ToolOutcome(
        content=json_content({"summary": summarise(plans), "results": items}),
        ui={"kind": "bulk_preview", "items": items},
        summary="پیش‌نمایش آغاز گروهی ارزیابی",
    )


@tool(
    name="run_bulk_evaluations",
    description="اجرای واقعی آغاز گروهی ارزیابی برای یک گروه. پرونده‌های تازه به دورهٔ باز و طرحِ فعال مهر می‌خورند؛ بلاک‌ها رد می‌شوند و در نتیجه می‌آیند.",
    category="دوره‌ها",
    risky=True,
    roles=(UserRole.hr,),
    parameters={
        "type": "object",
        "properties": {
            "org_unit": {"type": "string"},
            "only_managers": {"type": "boolean"},
            "contract_ends_before": {"type": "string"},
        },
    },
)
def run_bulk_evaluations(
    ctx: ToolContext, org_unit: str = "", only_managers: bool = False, contract_ends_before: str = ""
) -> ToolOutcome:
    from app.services.audit import log_event
    from app.services.bulk_evaluation import CohortFilter, execute, summarise

    db = ctx.db
    cohort = CohortFilter(
        org_unit=(org_unit or "").strip() or None,
        only_managers=bool(only_managers),
        contract_ends_before=_parse_date(contract_ends_before),
    )
    plans = execute(db, cohort)
    log_event(
        db,
        actor_user_id=ctx.user.id,
        event_type="evaluations_bulk_created",
        new_value={"summary": summarise(plans), "via": "ai_copilot"},
    )
    db.commit()
    items = [
        {
            "personnel_id": p.personnel_id,
            "full_name": p.full_name,
            "outcome": p.outcome.value,
            "evaluation_id": p.evaluation_id,
            "evaluation_code": p.evaluation_code,
            "reason": p.reason,
        }
        for p in plans
    ]
    return ToolOutcome(
        content=json_content({"summary": summarise(plans), "results": items}),
        ui={"kind": "bulk_preview", "items": items},
        summary="اجرای گروهی ارزیابی انجام شد",
    )


# ── برنامه‌های بهبود ───────────────────────────────────────────────────────


@tool(
    name="search_improvement_plans",
    description="فهرست برنامه‌های بهبود؛ غیر از منابع انسانی فقط برنامه‌هایی که پیگیری‌شان با شماست.",
    category="برنامه بهبود",
    read_only=True,
    roles=(UserRole.hr, UserRole.unit_supervisor, UserRole.deputy, UserRole.ceo),
    parameters={"type": "object", "properties": {"status": {"type": "string", "enum": ["open", "completed", "cancelled"]}, "limit": {"type": "integer"}}},
)
def search_improvement_plans(ctx: ToolContext, status: str = "", limit: int = 15) -> ToolOutcome:
    from app.models.improvement_plan import ImprovementPlan

    db = ctx.db
    stmt = select(ImprovementPlan)
    if ctx.user.role != UserRole.hr:
        stmt = stmt.where(ImprovementPlan.owner_user_id == ctx.user.id)
    if status:
        stmt = stmt.where(ImprovementPlan.status == status)
    rows = list(db.scalars(stmt.order_by(ImprovementPlan.id.desc()).limit(max(1, min(int(limit or 15), 50)))))
    names = dict(db.execute(select(PersonnelLite.id, PersonnelLite.full_name)))
    items = [
        {
            "id": p.id,
            "title": p.title,
            "personnel_name": names.get(p.personnel_id, "?"),
            "status": p.status.value,
            "review_date": p.review_date.isoformat() if p.review_date else None,
            "owner_user_id": p.owner_user_id,
        }
        for p in rows
    ]
    return ToolOutcome(
        content=json_content({"count": len(items), "plans": items}),
        ui={"kind": "plan_list", "items": items},
        summary=f"برنامه‌های بهبود ({len(items)} مورد)",
    )


from app.models.personnel import Personnel as PersonnelLite  # noqa: E402  (نام مستعارِ خوانا برای بالا)


@tool(
    name="create_improvement_plan",
    description="ساخت برنامهٔ بهبود برای یک پروندهٔ نهایی‌شدهٔ زیر آستانه، با اهداف و تاریخ بازبینی (منابع انسانی).",
    category="برنامه بهبود",
    risky=True,
    roles=(UserRole.hr,),
    parameters={
        "type": "object",
        "properties": {
            "evaluation_record_id": {"type": "integer"},
            "title": {"type": "string"},
            "review_date": {"type": "string"},
            "summary": {"type": "string"},
            "owner_user_id": {"type": "integer", "description": "مسئول پیگیری؛ خالی = خود منابع انسانی"},
            "goals": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["evaluation_record_id", "title", "review_date"],
    },
)
def create_improvement_plan(
    ctx: ToolContext,
    evaluation_record_id: int,
    title: str,
    review_date: str,
    summary: str = "",
    owner_user_id: int | None = None,
    goals: list | None = None,
) -> ToolOutcome:
    from app.api.routers.improvement_plans import create_plan as create_endpoint
    from app.schemas.improvement_plan import ImprovementPlanCreate

    plan = create_endpoint(
        payload=ImprovementPlanCreate(
            evaluation_record_id=int(evaluation_record_id),
            title=title,
            review_date=_parse_date(review_date),
            summary=(summary or "").strip() or None,
            owner_user_id=owner_user_id,
            goals=[str(g) for g in (goals or [])],
        ),
        db=ctx.db,
        current_user=ctx.user,
    )
    return ToolOutcome(
        content=json_content({"created": True, "plan": {"id": plan.id, "title": plan.title}}),
        summary=f"برنامهٔ بهبود «{plan.title}» ساخته شد",
    )


@tool(
    name="update_improvement_plan_goal",
    description="علامت‌زدن انجام‌شدن یکی از اهداف برنامهٔ بهبود. پیگیرِ برنامه مجاز است، نه فقط منابع انسانی. "
    "تغییرِ داده است و پس از تأیید کاربر اجرا می‌شود.",
    category="برنامه بهبود",
    risky=True,
    roles=(UserRole.hr, UserRole.unit_supervisor, UserRole.deputy, UserRole.ceo),
    parameters={
        "type": "object",
        "properties": {"goal_id": {"type": "integer"}, "is_done": {"type": "boolean"}},
        "required": ["goal_id"],
    },
)
def update_improvement_plan_goal(ctx: ToolContext, goal_id: int, is_done: bool = True) -> ToolOutcome:
    from app.models.improvement_plan import ImprovementPlanGoal

    db = ctx.db
    goal = db.get(ImprovementPlanGoal, int(goal_id))
    if goal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "هدفی با این شناسه پیدا نشد")
    plan = goal.plan
    if ctx.user.role != UserRole.hr and plan.owner_user_id != ctx.user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "پیگیری این برنامه با شما نیست")
    goal.is_done = bool(is_done)
    db.commit()
    return ToolOutcome(
        content=json_content({"updated": True, "goal_id": goal.id, "is_done": goal.is_done}),
        summary=f"هدف «{goal.description[:40]}» {'انجام‌شده علامت خورد' if is_done else 'باز شد'}",
    )


def _parse_date(value: object) -> date | None:
    from app.services.personnel_import import parse_flexible_date

    return parse_flexible_date(str(value or "").strip()) or None
