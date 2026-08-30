"""ابزارهای تحلیل و گزارش: خلاصهٔ گزارش، تفکیک واحد/شاخص، داشبوردها، گزارش رویدادها.

منبعِ اعداد همین‌جا `app.api.routers.reports` است — نه بازنویسیِ کوئری‌ها.
هر جا سرکوبِ کوهورت (k-ناشناسی) در رابط اعمال می‌شود، در دستیار هم همان
اعمال می‌شود؛ عددی که در گزارشِ HR نمایش داده نمی‌شود، از دهانِ دستیار هم
بیرون نمی‌آید.
"""
from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status

from app.models.enums import UserRole
from app.services.ai.tools.base import ToolContext, ToolOutcome, json_content, tool


def _hr_only(ctx: ToolContext) -> None:
    if ctx.user.role != UserRole.hr:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "این گزارش فقط برای منابع انسانی است")


def _parse_date(value: str | None) -> date | None:
    from app.services.personnel_import import parse_flexible_date

    return parse_flexible_date(str(value or "").strip()) or None


@tool(
    name="report_summary",
    description=(
        "گزارش تحلیلی ارزیابی‌های نهایی‌شده: شمار کل، میانگین نهایی، تفکیک میانگین به‌تفکیک واحد و به‌تفکیک شاخص. با "
        "فیلترهای دوره، واحد، بازهٔ تاریخ."
    ),
    category="گزارش",
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "period_id": {"type": "integer"},
            "org_unit": {"type": "string"},
            "created_from": {"type": "string"},
            "created_to": {"type": "string"},
        },
    },
)
def report_summary(
    ctx: ToolContext, period_id: int | None = None, org_unit: str = "", created_from: str = "", created_to: str = ""
) -> ToolOutcome:
    from app.api.routers.reports import _Filters, _summary_data

    _hr_only(ctx)
    filters = _Filters(
        period_id=period_id,
        org_unit=(org_unit or "").strip() or None,
        personnel_id=None,
        created_from=_parse_date(created_from),
        created_to=_parse_date(created_to),
        personnel_status=None,
        contract_end_from=None,
        contract_end_to=None,
    )
    db = ctx.db
    summary = _summary_data(db, filters)
    payload = summary.model_dump(mode="json")
    return ToolOutcome(
        content=json_content(payload),
        ui={"kind": "report_summary", "summary": payload},
        summary="خلاصهٔ گزارش ارزیابی‌های نهایی‌شده",
    )


@tool(
    name="employee_vs_unit",
    description="مقایسهٔ امتیاز یک فرد با میانگین واحد خودش (ارزیابی نهایی‌شده؛ با رعایت سرکوب کوهورت).",
    category="گزارش",
    read_only=True,
    parameters={
        "type": "object",
        "properties": {"personnel_id": {"type": "integer"}, "period_id": {"type": "integer"}},
        "required": ["personnel_id"],
    },
)
def employee_vs_unit(ctx: ToolContext, personnel_id: int, period_id: int | None = None) -> ToolOutcome:
    from app.api.routers.reports import employee_vs_unit as employee_vs_unit_endpoint

    _hr_only(ctx)
    db = ctx.db
    data = employee_vs_unit_endpoint(
        personnel_id=int(personnel_id),
        period_id=period_id,
        created_from=None,
        created_to=None,
        db=db,
        current_user=ctx.user,
    )
    return ToolOutcome(
        content=json_content(data.model_dump(mode="json") if hasattr(data, "model_dump") else data),
        summary="مقایسهٔ فرد با میانگین واحد",
    )


@tool(
    name="dashboard_overview",
    description=(
        "کارت‌های خلاصهٔ داشبورد منابع انسانی: شمار پرسنل، پرونده‌های در جریان، نهایی‌شده‌ها، قراردادهای رو به اتمام."
    ),
    category="گزارش",
    read_only=True,
    parameters={"type": "object", "properties": {}},
)
def dashboard_overview(ctx: ToolContext) -> ToolOutcome:
    from app.api.routers.dashboard import overview as overview_endpoint

    _hr_only(ctx)
    db = ctx.db
    payload = overview_endpoint(site=None, db=db, current_user=ctx.user).model_dump(mode="json")
    return ToolOutcome(content=json_content(payload), summary="خلاصهٔ داشبورد سازمان")


@tool(
    name="expiring_contracts",
    description="پرسنلِ فعالِ قراردادش رو به اتمام است یا منقضی شده — ورودیِ طبیعی تصمیم تمدید.",
    category="گزارش",
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "days": {"type": "integer", "description": "پیش‌فرض ۶۰ روز"},
            "include_expired": {"type": "boolean"},
        },
    },
)
def expiring_contracts(ctx: ToolContext, days: int = 60, include_expired: bool = True) -> ToolOutcome:
    from app.api.routers.dashboard import expiring_contracts as expiring_endpoint

    _hr_only(ctx)
    db = ctx.db
    rows = expiring_endpoint(days=max(1, min(int(days or 60), 365)), db=db, current_user=ctx.user)
    items = [r.model_dump(mode="json") for r in rows]
    if not include_expired:
        items = [i for i in items if i.get("days_remaining", 0) >= 0]
    return ToolOutcome(
        content=json_content({"count": len(items), "contracts": items}),
        ui={"kind": "person_list", "items": items},
        summary=f"قراردادهای رو به اتمام ({len(items)} مورد)",
    )


@tool(
    name="executive_analysis",
    description="تحلیل سازمان برای مدیرعامل/معاونت: میانگین به‌تفکیک واحد با قواعد طرح فعال (با سرکوب کوهورت).",
    category="گزارش",
    read_only=True,
    roles=(UserRole.ceo, UserRole.deputy),
    parameters={"type": "object", "properties": {}},
)
def executive_analysis(ctx: ToolContext) -> ToolOutcome:
    from app.api.routers.analytics import executive_overview

    db = ctx.db
    payload = executive_overview(db=db, current_user=ctx.user).model_dump(mode="json")
    return ToolOutcome(content=json_content(payload), summary="تحلیل سازمان")


@tool(
    name="my_scoring_analysis",
    description="الگوی نمره‌دهی خود ارزیاب در برابر بقیهٔ سازمان.",
    category="گزارش",
    read_only=True,
    roles=(UserRole.unit_supervisor, UserRole.deputy),
    parameters={"type": "object", "properties": {}},
)
def my_scoring_analysis(ctx: ToolContext) -> ToolOutcome:
    from app.api.routers.analytics import my_scoring_profile

    db = ctx.db
    payload = my_scoring_profile(db=db, current_user=ctx.user).model_dump(mode="json")
    return ToolOutcome(content=json_content(payload), summary="الگوی نمره‌دهی شما")


@tool(
    name="search_audit_log",
    description=(
        "گزارش رویدادهای سامانه — در همان دو دامنهٔ دیدِ رابط: «گزارش کامل» یا فقط رویدادهای سامانه‌ای. فیلتر بر نوع "
        "رویداد، کاربر، پرونده و بازه."
    ),
    category="گزارش",
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "event_type": {"type": "string"},
            "actor_user_id": {"type": "integer"},
            "evaluation_record_id": {"type": "integer"},
            "created_from": {"type": "string"},
            "created_to": {"type": "string"},
            "limit": {"type": "integer"},
        },
    },
)
def search_audit_log(
    ctx: ToolContext,
    event_type: str = "",
    actor_user_id: int | None = None,
    evaluation_record_id: int | None = None,
    created_from: str = "",
    created_to: str = "",
    limit: int = 20,
) -> ToolOutcome:
    from sqlalchemy import select

    from app.api.deps import capabilities_of
    from app.models.audit_log import AuditLog
    from app.models.enums import Capability
    from app.models.user import User

    db = ctx.db
    caps = capabilities_of(db, ctx.user.id)
    can_full = Capability.view_audit_log in caps
    can_diag = Capability.view_diagnostics in caps
    if not (can_full or can_diag):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "به گزارش رویدادها دسترسی ندارید")

    stmt = select(AuditLog)
    if event_type:
        stmt = stmt.where(AuditLog.event_type == event_type.strip())
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == int(actor_user_id))
    if evaluation_record_id:
        stmt = stmt.where(AuditLog.evaluation_record_id == int(evaluation_record_id))
    from_dt = _parse_date(created_from)
    to_dt = _parse_date(created_to)
    if from_dt:
        stmt = stmt.where(AuditLog.created_at >= from_dt)
    if to_dt:
        from datetime import timedelta

        stmt = stmt.where(AuditLog.created_at < to_dt + timedelta(days=1))
    # دامنهٔ دید: دارندهٔ گزارش کامل همه‌چیز؛ دارندهٔ سلامت فقط رویدادهای سامانه‌ای
    if not can_full:
        system_events = {
            "user_login", "user_login_failed", "account_locked", "ai_settings_changed",
            "ai_access_changed", "ai_tool_invoked", "ai_tool_failed", "ai_action_confirmed",
            "ai_action_rejected", "capabilities_changed",
        }
        stmt = stmt.where(AuditLog.event_type.in_(system_events))

    rows = list(db.scalars(stmt.order_by(AuditLog.id.desc()).limit(max(1, min(int(limit or 20), 100)))))
    actor_ids = {r.actor_user_id for r in rows if r.actor_user_id}
    usernames = (
        dict(db.execute(select(User.id, User.username).where(User.id.in_(actor_ids))))
        if actor_ids
        else {}
    )
    items = [
        {
            "id": r.id,
            "event_type": r.event_type,
            "actor": usernames.get(r.actor_user_id),
            "evaluation_record_id": r.evaluation_record_id,
            "new_value": r.new_value,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ToolOutcome(
        content=json_content({"count": len(items), "events": items}),
        summary=f"گزارش رویدادها ({len(items)} رویداد)",
    )


@tool(
    name="my_permissions",
    description="مجوزهای اداری و نقشِ خود شما — برای پاسخ به «چه کاری از دستم برمی‌آید».",
    category="گزارش",
    read_only=True,
    parameters={"type": "object", "properties": {}},
)
def my_permissions(ctx: ToolContext) -> ToolOutcome:
    from app.services.ai.tools.base import allowed_tools
    from app.services.authorization import capabilities_of

    db = ctx.db
    caps = capabilities_of(db, ctx.user.id)
    tools = allowed_tools(ctx.user, caps, allow_writes=True)
    payload = {
        "role": ctx.user.role.value,
        "capabilities": sorted(c.value for c in caps),
        "tool_count": len(tools),
        "tool_categories": sorted({t.category for t in tools}),
    }
    return ToolOutcome(content=json_content(payload), summary="مجوزهای شما در سامانه")
