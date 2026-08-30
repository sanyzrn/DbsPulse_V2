"""ابزارهای «آدم‌ها»: پرسنل، حساب‌ها، واحدها، زنجیرهٔ ارزیابی، مجوزها.

هر ابزار از همان سرویس‌ها و همان قواعدِ رابط استفاده می‌کند:
دیدِ سطری مثل فهرستِ پرسنل، گاردهای خودارزیابی مثل فرمِ دسترسی، و ممنوعیتِ
«مسئول واحد در حالِ پروندهٔ باز» مثل PATCH پرسنل. تفاوتِ این‌جا با رابط فقط
شکلِ درخواست است، نه قاعده.
"""
from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import Capability, PersonnelStatus, UserRole
from app.models.evaluation import EvaluationRecord
from app.models.evaluation_access import EvaluationAccess
from app.models.personnel import Personnel
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.services.ai.tools.base import ToolContext, ToolOutcome, json_content, tool
from app.services.audit import log_event
from app.services.org_unit import split_site
from app.services.self_evaluation import (
    ensure_chain_stages_are_not_redundant,
    ensure_evaluators_are_not_the_subject,
)
from app.services.workflow import IS_OPEN_RECORD

ORG_WIDE_ROLES = (UserRole.hr, UserRole.deputy, UserRole.ceo, UserRole.support)

_ROLE_LABELS = {
    UserRole.hr: "منابع انسانی",
    UserRole.unit_supervisor: "مسئول واحد",
    UserRole.deputy: "معاونت",
    UserRole.ceo: "مدیرعامل",
    UserRole.employee: "کارمند",
    UserRole.support: "مدیر سامانه",
}


def _visible_personnel_ids(db: Session, user: CurrentUser) -> set[int] | None:
    """None یعنی همه — دقیقاً مثل متنِ زمینه و فهرستِ پرسنلِ رابط."""
    if user.role in ORG_WIDE_ROLES:
        return None
    rows = db.scalars(
        select(EvaluationAccess.personnel_id).where(
            (EvaluationAccess.unit_supervisor_user_id == user.id)
            | (EvaluationAccess.deputy_user_id == user.id)
            | (EvaluationAccess.ceo_user_id == user.id)
        )
    )
    ids = set(rows)
    if user.personnel_id:
        ids.add(user.personnel_id)
    return ids


def _person_or_404(db: Session, personnel_id: int) -> Personnel:
    person = db.get(Personnel, int(personnel_id))
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پرسنلی با این شناسه پیدا نشد")
    return person


def _ensure_can_view_personnel(
    db: Session, person: Personnel, user: CurrentUser
) -> None:
    """همان قاعدهٔ GET /personnel/{id}: منابع انسانی و زنجیره و خودِ فرد."""
    if user.role in (UserRole.hr,):
        return
    if user.role in (UserRole.deputy, UserRole.ceo, UserRole.support):
        return  # نقش‌های سازمان‌گیر در فهرست پرسنلِ رابط هم کامل می‌بینند
    access = db.scalar(
        select(EvaluationAccess).where(EvaluationAccess.personnel_id == person.id)
    )
    chain = {access.unit_supervisor_user_id, access.deputy_user_id, access.ceo_user_id} if access else set()
    if user.id in chain or user.personnel_id == person.id:
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "به این پرسنل دسترسی ندارید")


def _person_payload(db: Session, person: Personnel) -> dict:
    """چیزی که هم مدل می‌بیند هم کارتِ رابط — بدون فیلدهای حساسِ اضافه."""
    account = db.scalar(select(User).where(User.personnel_id == person.id))
    open_record = db.scalar(
        select(EvaluationRecord).where(
            EvaluationRecord.subject_personnel_id == person.id,
            IS_OPEN_RECORD,
        )
    )
    access = db.scalar(
        select(EvaluationAccess).where(EvaluationAccess.personnel_id == person.id)
    )
    seat_names = {}
    if access:
        ids = {access.unit_supervisor_user_id, access.deputy_user_id, access.ceo_user_id} - {None}
        if ids:
            seat_names = dict(db.execute(select(User.id, User.username).where(User.id.in_(ids))))
    site, unit = split_site(person.org_unit)
    return {
        "id": person.id,
        "personnel_code": person.personnel_code,
        "full_name": person.full_name,
        "job_title": person.job_title,
        "org_unit": person.org_unit,
        "site": site or "",
        "unit": unit,
        "is_manager": person.is_manager,
        "status": person.status.value,
        "contract_start_date": person.contract_start_date.isoformat(),
        "contract_end_date": person.contract_end_date.isoformat(),
        "separation_date": person.separation_date.isoformat() if person.separation_date else None,
        "separation_reason": person.separation_reason.value if person.separation_reason else None,
        "account_username": account.username if account else None,
        "open_evaluation_id": open_record.id if open_record else None,
        "chain": (
            {
                "unit_supervisor": seat_names.get(access.unit_supervisor_user_id),
                "deputy": seat_names.get(access.deputy_user_id),
                "ceo": seat_names.get(access.ceo_user_id),
            }
            if access
            else None
        ),
    }


# ── پرسنل ──────────────────────────────────────────────────────────────────


@tool(
    name="search_personnel",
    description=(
        "جست‌وجوی پرسنل با نام، کد پرسنلی، واحد سازمانی، وضعیت یا تاریخ پایان قرارداد. برای یافتن شناسهٔ فرد پیش از هر "
        "تغییر لازم است."
    ),
    category="پرسنل",
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "q": {"type": "string", "description": "بخشی از نام یا کد پرسنلی"},
            "org_unit": {"type": "string", "description": "نام دقیق واحد سازمانی"},
            "status": {"type": "string", "enum": ["active", "inactive"]},
            "contract_ends_before": {
                "type": "string",
                "description": "تاریخ YYYY-MM-DD؛ فقط پرسنلی که قراردادش پیش از این تاریخ تمام می‌شود",
            },
            "is_manager": {"type": "boolean"},
            "limit": {"type": "integer", "description": "پیش‌فرض ۱۵، حداکثر ۵۰"},
        },
    },
)
def search_personnel(
    ctx: ToolContext,
    q: str = "",
    org_unit: str = "",
    status: str = "",
    contract_ends_before: str = "",
    is_manager: bool | None = None,
    limit: int = 15,
) -> ToolOutcome:
    db = ctx.db
    stmt = select(Personnel)
    visible = _visible_personnel_ids(db, ctx.user)
    if visible is not None:
        stmt = stmt.where(Personnel.id.in_(visible or [0]))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(Personnel.full_name.ilike(pattern), Personnel.personnel_code.ilike(pattern))
        )
    if org_unit:
        stmt = stmt.where(Personnel.org_unit.ilike(f"%{org_unit.strip()}%"))
    if status:
        stmt = stmt.where(Personnel.status == PersonnelStatus(status))
    if is_manager is not None:
        stmt = stmt.where(Personnel.is_manager.is_(bool(is_manager)))
    if contract_ends_before:
        end = _parse_date(contract_ends_before)
        if end is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "تاریخ پایان بازه خوانده نشد (نمونه: 2026-01-01)")
        stmt = stmt.where(Personnel.contract_end_date <= end)
    stmt = stmt.order_by(Personnel.full_name).limit(max(1, min(int(limit or 15), 50)))
    people = list(db.scalars(stmt))
    items = [
        {
            "id": p.id,
            "full_name": p.full_name,
            "personnel_code": p.personnel_code,
            "job_title": p.job_title,
            "org_unit": p.org_unit,
            "status": p.status.value,
            "contract_end_date": p.contract_end_date.isoformat(),
            "is_manager": p.is_manager,
        }
        for p in people
    ]
    return ToolOutcome(
        content=json_content({"matches": len(items), "personnel": items}),
        ui={"kind": "person_list", "items": items},
        summary=f"جست‌وجوی پرسنل ({len(items)} نتیجه)",
    )


def _describe_search(q="", org_unit="", **_):
    parts = [v for v in (q, org_unit) if v]
    return "جست‌وجوی پرسنل" + (" «" + "، ".join(parts) + "»" if parts else "")


search_personnel.describe = _describe_search


@tool(
    name="get_personnel",
    description="نمای کامل یک پرسنل: قرارداد، حساب کاربری، زنجیرهٔ ارزیابی و پروندهٔ بازش.",
    category="پرسنل",
    read_only=True,
    parameters={
        "type": "object",
        "properties": {"personnel_id": {"type": "integer"}},
        "required": ["personnel_id"],
    },
)
def get_personnel(ctx: ToolContext, personnel_id: int) -> ToolOutcome:
    person = _person_or_404(ctx.db, personnel_id)
    _ensure_can_view_personnel(ctx.db, person, ctx.user)
    payload = _person_payload(ctx.db, person)
    return ToolOutcome(
        content=json_content(payload),
        ui={"kind": "person_card", "person": payload},
        summary=f"مشاهدهٔ پروندهٔ {person.full_name}",
    )


@tool(
    name="create_personnel",
    description="ثبت پرسنل تازه. کد پرسنلی باید یکتا باشد. ساخت حساب کاربری و زنجیره، گام‌های جداگانه‌اند.",
    category="پرسنل",
    risky=True,
    capabilities=(Capability.manage_personnel,),
    roles=(UserRole.hr,),
    parameters={
        "type": "object",
        "properties": {
            "full_name": {"type": "string"},
            "personnel_code": {"type": "string"},
            "job_title": {"type": "string"},
            "org_unit": {"type": "string", "description": "واحد سازمانی؛ با «محل / واحد» اگر محل دارید"},
            "is_manager": {"type": "boolean"},
            "contract_start_date": {"type": "string", "description": "YYYY-MM-DD؛ پیش‌فرض امروز"},
            "contract_end_date": {"type": "string", "description": "YYYY-MM-DD؛ الزامی"},
        },
        "required": ["full_name", "personnel_code", "job_title", "org_unit", "contract_end_date"],
    },
)
def create_personnel(
    ctx: ToolContext,
    full_name: str,
    personnel_code: str,
    job_title: str,
    org_unit: str,
    contract_end_date: str,
    is_manager: bool = False,
    contract_start_date: str = "",
) -> ToolOutcome:
    db = ctx.db
    if db.scalar(select(Personnel).where(Personnel.personnel_code == personnel_code.strip())):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این کد پرسنلی از قبل ثبت شده است")
    end = _parse_date(contract_end_date)
    if end is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تاریخ پایان قرارداد خوانده نشد (نمونه: 2026-01-01)")
    start = _parse_date(contract_start_date) or date.today()
    if end <= start:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "«پایان قرارداد» باید بعد از «شروع قرارداد» باشد")
    person = Personnel(
        personnel_code=personnel_code.strip(),
        full_name=full_name.strip()[:200],
        job_title=job_title.strip()[:150],
        org_unit=org_unit.strip()[:150],
        is_manager=bool(is_manager),
        contract_start_date=start,
        contract_end_date=end,
        status=PersonnelStatus.active,
        created_by_user_id=ctx.user.id,
    )
    db.add(person)
    db.flush()
    log_event(
        db,
        actor_user_id=ctx.user.id,
        event_type="personnel_created",
        new_value={
            "id": person.id,
            "personnel_code": person.personnel_code,
            "full_name": person.full_name,
            "via": "ai_copilot",
        },
    )
    db.commit()
    payload = _person_payload(db, person)
    return ToolOutcome(
        content=json_content({"created": True, "person": payload}),
        ui={"kind": "person_card", "person": payload},
        summary=f"پرسنل «{person.full_name}» با کد {person.personnel_code} ثبت شد",
    )


def _describe_create_personnel(full_name, personnel_code, org_unit="", job_title="", **_):
    return (
        f"ثبت «{full_name}» با کد {personnel_code}"
        + (f" به‌عنوان {job_title}" if job_title else "")
        + (f" در واحد {org_unit}" if org_unit else "")
    )


create_personnel.describe = _describe_create_personnel


@tool(
    name="update_personnel",
    description="ویرایش پرسنل موجود: شغل، واحد، تاریخ‌های قرارداد. خروج از سازمان (غیرفعال‌کردن) قاعدهٔ جداگانه‌ای دارد.",
    category="پرسنل",
    risky=True,
    capabilities=(Capability.manage_personnel,),
    roles=(UserRole.hr,),
    parameters={
        "type": "object",
        "properties": {
            "personnel_id": {"type": "integer"},
            "job_title": {"type": "string"},
            "org_unit": {"type": "string"},
            "is_manager": {"type": "boolean"},
            "contract_end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        "required": ["personnel_id"],
    },
)
def update_personnel(
    ctx: ToolContext,
    personnel_id: int,
    job_title: str | None = None,
    org_unit: str | None = None,
    is_manager: bool | None = None,
    contract_end_date: str | None = None,
) -> ToolOutcome:
    db = ctx.db
    person = _person_or_404(db, personnel_id)
    before: dict[str, object] = {}
    fields: dict[str, object] = {}
    if job_title is not None:
        fields["job_title"] = job_title.strip()[:150]
    if org_unit is not None:
        fields["org_unit"] = org_unit.strip()[:150]
    if is_manager is not None:
        fields["is_manager"] = bool(is_manager)
    if contract_end_date is not None:
        end = _parse_date(contract_end_date)
        if end is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "تاریخ پایان قرارداد خوانده نشد")
        fields["contract_end_date"] = end
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فیلدی برای تغییر داده نشده است")

    # تغییر «مدیر بودن» وقتی پروندهٔ بازی هست ممنوع است — همان قانونِ PATCH رابط.
    if "is_manager" in fields and fields["is_manager"] != person.is_manager:
        open_record = db.scalar(
            select(EvaluationRecord).where(
                EvaluationRecord.subject_personnel_id == person.id, IS_OPEN_RECORD
            )
        )
        if open_record is not None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "این پرسنل پروندهٔ ارزیابی باز دارد؛ تغییر «مدیر بودن» تا تعیین تکلیف پرونده ممکن نیست",
            )

    for key, value in fields.items():
        before[key] = str(getattr(person, key))
        setattr(person, key, value)

    log_event(
        db,
        actor_user_id=ctx.user.id,
        event_type="personnel_updated",
        old_value={"id": person.id, **{k: str(v) for k, v in before.items()}},
        new_value={"id": person.id, **{k: str(v) for k, v in fields.items()}, "via": "ai_copilot"},
    )
    db.commit()
    payload = _person_payload(db, person)
    changed = "، ".join(fields)
    return ToolOutcome(
        content=json_content({"updated": True, "changed": list(map(str, fields)), "person": payload}),
        ui={"kind": "person_card", "person": payload},
        summary=f"پروندهٔ «{person.full_name}» به‌روز شد ({changed})",
    )


def _describe_update_personnel(
    personnel_id, job_title=None, org_unit=None, contract_end_date=None, is_manager=None, **_
):
    bits = []
    if job_title:
        bits.append(f"عنوان شغلی به «{job_title}»")
    if org_unit:
        bits.append(f"واحد به «{org_unit}»")
    if contract_end_date:
        bits.append(f"پایان قرارداد به {contract_end_date}")
    if is_manager is not None:
        bits.append("نشانِ مدیر" + (" بله" if is_manager else " خیر"))
    return f"ویرایش پرسنل #{personnel_id}" + (" (" + "، ".join(bits) + ")" if bits else "")


update_personnel.describe = _describe_update_personnel


@tool(
    name="separate_personnel",
    description=(
        "ثبت خروج پرسنل از سازمان (استعفا، اخراج، پایان قرارداد، بازنشستگی، سایر). حسابش بسته و پروندهٔ بازش لغو می‌شود "
        "— کنشِ سنگین با تأیید."
    ),
    category="پرسنل",
    risky=True,
    capabilities=(Capability.manage_personnel,),
    roles=(UserRole.hr,),
    parameters={
        "type": "object",
        "properties": {
            "personnel_id": {"type": "integer"},
            "separation_date": {"type": "string", "description": "YYYY-MM-DD؛ پیش‌فرض امروز"},
            "separation_reason": {
                "type": "string",
                "enum": ["resignation", "dismissal", "contract_end", "retirement", "other"],
            },
        },
        "required": ["personnel_id", "separation_reason"],
    },
)
def separate_personnel(
    ctx: ToolContext, personnel_id: int, separation_reason: str, separation_date: str = ""
) -> ToolOutcome:
    db = ctx.db
    person = _person_or_404(db, personnel_id)
    reason = separation_reason.strip()
    if reason not in {"resignation", "dismissal", "contract_end", "retirement", "other"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "علت خروج نامعتبر است")
    person.status = PersonnelStatus.inactive
    person.separation_reason = reason
    person.separation_date = _parse_date(separation_date) or date.today()

    # پروندهٔ باز: لغو با دلیل — همان مسیرِ رسمیِ گردش‌کار.
    open_record = db.scalar(
        select(EvaluationRecord).where(
            EvaluationRecord.subject_personnel_id == person.id, IS_OPEN_RECORD
        )
    )
    cancelled = False
    if open_record is not None:
        from app.services.workflow import apply_transition

        apply_transition(db, open_record, "cancel", ctx.user)
        cancelled = True

    account = db.scalar(select(User).where(User.personnel_id == person.id))
    if account is not None and account.is_active:
        account.is_active = False
        account.token_version += 1
        from app.services.sessions import revoke_all_for_user

        revoke_all_for_user(account.id)

    log_event(
        db,
        actor_user_id=ctx.user.id,
        event_type="personnel_departed",
        new_value={
            "id": person.id,
            "separation_reason": reason,
            "separation_date": person.separation_date.isoformat(),
            "open_evaluation_cancelled": cancelled,
            "via": "ai_copilot",
        },
    )
    db.commit()
    label = {
        "resignation": "استعفا", "dismissal": "اخراج", "contract_end": "پایان قرارداد",
        "retirement": "بازنشستگی", "other": "سایر",
    }[reason]
    return ToolOutcome(
        content=json_content({
            "separated": True,
            "person": _person_payload(db, person),
            "open_evaluation_cancelled": cancelled,
        }),
        summary=f"خروج «{person.full_name}» با علت {label} ثبت شد",
    )


# ── حساب‌های کاربری ────────────────────────────────────────────────────────


@tool(
    name="search_users",
    description="جست‌وجوی حساب‌های کاربری با نقش، نام کاربری یا وضعیت فعال/غیرفعال.",
    category="حساب‌ها",
    read_only=True,
    capabilities=(Capability.manage_users,),
    parameters={
        "type": "object",
        "properties": {
            "q": {"type": "string"},
            "role": {"type": "string", "enum": [r.value for r in UserRole]},
            "is_active": {"type": "boolean"},
            "limit": {"type": "integer"},
        },
    },
)
def search_users(
    ctx: ToolContext, q: str = "", role: str = "", is_active: bool | None = None, limit: int = 20
) -> ToolOutcome:
    db = ctx.db
    stmt = select(User)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.username.ilike(pattern), User.full_name.ilike(pattern)))
    if role:
        stmt = stmt.where(User.role == UserRole(role))
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(bool(is_active)))
    stmt = stmt.order_by(User.id).limit(max(1, min(int(limit or 20), 50)))
    users = list(db.scalars(stmt))
    items = [
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name or "",
            "role": u.role.value,
            "role_label": _ROLE_LABELS.get(u.role, u.role.value),
            "is_active": u.is_active,
            "personnel_id": u.personnel_id,
        }
        for u in users
    ]
    return ToolOutcome(
        content=json_content({"matches": len(items), "users": items}),
        ui={"kind": "user_list", "items": items},
        summary=f"جست‌وجوی حساب‌ها ({len(items)} نتیجه)",
    )


def _describe_search_users(q="", role="", **_):
    return "جست‌وجوی حساب‌ها" + (f" برای «{q}»" if q else "") + (f" با نقش {role}" if role else "")


search_users.describe = _describe_search_users


@tool(
    name="create_user",
    description="ساخت حساب کاربری. نقش کارمند باید به پرسنل گره بخورد. رمز هرگز در لاگ نمی‌نشیند.",
    category="حساب‌ها",
    risky=True,
    capabilities=(Capability.manage_users,),
    parameters={
        "type": "object",
        "properties": {
            "username": {"type": "string", "description": "حروف انگلیسی، رقم، نقطه و خط تیره"},
            "password": {"type": "string", "description": "دست‌کم ۱۰ نویسه؛ خالی = رمز موقتِ خودکار"},
            "role": {"type": "string", "enum": [r.value for r in UserRole]},
            "personnel_id": {"type": "integer", "description": "برای نقش کارمند الزامی"},
            "full_name": {"type": "string"},
        },
        "required": ["username", "role"],
    },
)
def create_user(
    ctx: ToolContext,
    username: str,
    role: str,
    password: str = "",
    personnel_id: int | None = None,
    full_name: str = "",
) -> ToolOutcome:
    from app.core.security import hash_password
    from app.services.authorization import apply_default_hr_capabilities
    from app.services.security_tokens import generate_temp_password
    from app.services.self_evaluation import ensure_user_link_is_not_self_evaluation

    db = ctx.db
    username = username.strip()
    if not username or len(username) < 3:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نام کاربری باید دست‌کم ۳ نویسه باشد")
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این نام کاربری از قبل وجود دارد")
    role_value = UserRole(role)
    if role_value == UserRole.employee:
        if personnel_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "حسابِ کارمند باید به پرسنل گره بخورد")
        person = db.get(Personnel, int(personnel_id))
        if person is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "پرسنلی با این شناسه پیدا نشد")
    generated = ""
    plain = (password or "").strip()
    if not plain:
        plain = generate_temp_password()
        generated = plain
    if len(plain) < 10:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "رمز باید دست‌کم ۱۰ نویسه باشد")
    user = User(
        username=username,
        password_hash=hash_password(plain),
        role=role_value,
        personnel_id=int(personnel_id) if personnel_id else None,
        full_name=(full_name or "").strip() or None,
        is_active=True,
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    if role_value == UserRole.hr:
        apply_default_hr_capabilities(db, user.id)
    if user.personnel_id:
        ensure_user_link_is_not_self_evaluation(db, user, user.personnel_id)
    log_event(
        db,
        actor_user_id=ctx.user.id,
        event_type="user_created",
        new_value={"id": user.id, "username": user.username, "role": user.role.value, "via": "ai_copilot"},
    )
    db.commit()
    content = {"created": True, "user": {"id": user.id, "username": user.username, "role": user.role.value}}
    if generated:
        content["temporary_password"] = generated
        content["note"] = "این رمز فقط همین‌جا نشان داده می‌شود؛ کاربر در اولین ورود باید عوضش کند."
    return ToolOutcome(
        content=json_content(content),
        ui={"kind": "user_created", "user": content.get("user"), "temporary_password": generated},
        summary=f"حساب «{user.username}» با نقش {_ROLE_LABELS.get(user.role)} ساخته شد",
    )


def _describe_create_user(username, role, **_):
    return f"ساخت حساب «{username}» با نقش {_ROLE_LABELS.get(UserRole(role), role)}"


create_user.describe = _describe_create_user


@tool(
    name="update_user",
    description="تغییر حساب کاربری: نقش، فعال/غیرفعال، رمز، نام. غیرفعال‌کردن یعنی بستن همهٔ نشست‌ها.",
    category="حساب‌ها",
    risky=True,
    capabilities=(Capability.manage_users,),
    parameters={
        "type": "object",
        "properties": {
            "user_id": {"type": "integer"},
            "role": {"type": "string", "enum": [r.value for r in UserRole]},
            "is_active": {"type": "boolean"},
            "password": {"type": "string"},
            "full_name": {"type": "string"},
            "personnel_id": {"type": "integer"},
        },
        "required": ["user_id"],
    },
)
def update_user(
    ctx: ToolContext,
    user_id: int,
    role: str | None = None,
    is_active: bool | None = None,
    password: str | None = None,
    full_name: str | None = None,
    personnel_id: int | None = None,
) -> ToolOutcome:
    from app.core.security import hash_password
    from app.services.authorization import apply_default_hr_capabilities
    from app.services.self_evaluation import ensure_user_link_is_not_self_evaluation
    from app.services.sessions import revoke_all_for_user

    db = ctx.db
    account = db.get(User, int(user_id))
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حسابی با این شناسه پیدا نشد")
    changes: dict[str, object] = {}

    if role is not None and role != account.role.value:
        account.role = UserRole(role)
        changes["role"] = role
        if account.role == UserRole.hr:
            apply_default_hr_capabilities(db, account.id)
    if is_active is not None and is_active != account.is_active:
        if account.id == ctx.user.id and is_active is False:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "نمی‌توانید حساب خودتان را غیرفعال کنید")
        account.is_active = is_active
        changes["is_active"] = is_active
        if not is_active:
            account.token_version += 1
            revoke_all_for_user(account.id)
    if password:
        if len(password) < 10:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "رمز باید دست‌کم ۱۰ نویسه باشد")
        account.password_hash = hash_password(password)
        account.token_version += 1
        revoke_all_for_user(account.id)
        changes["password"] = "changed"
    if full_name is not None:
        account.full_name = full_name.strip() or None
        changes["full_name"] = account.full_name
    if personnel_id is not None and personnel_id != account.personnel_id:
        ensure_user_link_is_not_self_evaluation(db, account, int(personnel_id))
        account.personnel_id = int(personnel_id)
        changes["personnel_id"] = account.personnel_id

    if not changes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تغییری داده نشده است")

    log_event(
        db,
        actor_user_id=ctx.user.id,
        event_type="user_updated",
        old_value={"id": account.id},
        new_value={"id": account.id, "via": "ai_copilot", **changes},
    )
    db.commit()
    return ToolOutcome(
        content=json_content(
            {
                "updated": True,
                "user": {"id": account.id, "username": account.username},
                "changes": {k: str(v) for k, v in changes.items()},
            }
        ),
        summary=f"حساب «{account.username}» به‌روز شد",
    )


def _describe_update_user(user_id, role=None, is_active=None, password=None, full_name=None, **_):
    bits = []
    if role:
        bits.append(f"نقش به {role}")
    if is_active is not None:
        bits.append("فعال‌سازی" if is_active else "غیرفعال‌سازی")
    if password:
        bits.append("تغییر رمز")
    if full_name:
        bits.append(f"نام به «{full_name}»")
    return f"ویرایش حساب #{user_id}" + (" (" + "، ".join(bits) + ")" if bits else "")


update_user.describe = _describe_update_user


# ── واحدهای سازمانی ────────────────────────────────────────────────────────


@tool(
    name="list_org_units",
    description="فهرست واحدهای سازمانی با شمارِ پرسنل هر واحد.",
    category="سازمان",
    read_only=True,
    parameters={"type": "object", "properties": {"include_inactive": {"type": "boolean"}}},
)
def list_org_units(ctx: ToolContext, include_inactive: bool = False) -> ToolOutcome:
    from app.models.org_unit import OrgUnit

    db = ctx.db
    stmt = select(OrgUnit)
    if not include_inactive:
        stmt = stmt.where(OrgUnit.is_active.is_(True))
    stmt = stmt.order_by(OrgUnit.display_order, OrgUnit.id)
    units = list(db.scalars(stmt))
    counts = dict(
        db.execute(
            select(Personnel.org_unit, func.count())
            .group_by(Personnel.org_unit)
        ).all()
    )
    items = [
        {
            "id": u.id,
            "full_name": u.full_name,
            "site": u.site or "",
            "name": u.name,
            "is_active": u.is_active,
            "personnel_count": int(counts.get(u.full_name, 0)),
        }
        for u in units
    ]
    return ToolOutcome(
        content=json_content({"org_units": items}),
        ui={"kind": "org_unit_list", "items": items},
        summary=f"فهرست واحدها ({len(items)} واحد)",
    )


@tool(
    name="create_org_unit",
    description="افزودن واحد سازمانی تازه؛ می‌تواند زیر یک «محل» (مثل کارخانه) باشد.",
    category="سازمان",
    risky=True,
    capabilities=(Capability.manage_personnel,),
    roles=(UserRole.hr,),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "site": {"type": "string", "description": "محل سازمانی؛ خالی یعنی بدون محل"},
        },
        "required": ["name"],
    },
)
def create_org_unit(ctx: ToolContext, name: str, site: str = "") -> ToolOutcome:
    from app.models.org_unit import OrgUnit
    from app.services.org_unit import join_site

    db = ctx.db
    unit_name = name.strip()[:150]
    site_name = site.strip()[:100]
    full = join_site(site_name, unit_name)
    existing = db.scalar(select(OrgUnit).where(OrgUnit.name == unit_name, OrgUnit.site == (site_name or None)))
    if existing is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"واحد «{full}» از قبل وجود دارد")
    unit = OrgUnit(site=site_name or None, name=unit_name, is_active=True)
    db.add(unit)
    db.flush()
    log_event(
        db,
        actor_user_id=ctx.user.id,
        event_type="org_unit_created",
        new_value={"id": unit.id, "full_name": unit.full_name, "via": "ai_copilot"},
    )
    db.commit()
    return ToolOutcome(
        content=json_content({"created": True, "org_unit": {"id": unit.id, "full_name": unit.full_name}}),
        summary=f"واحد «{unit.full_name}» افزوده شد",
    )


def _describe_create_org_unit(name, site="", **_):
    return f"افزودن واحد «{name}»" + (f" در محل {site}" if site else "")


create_org_unit.describe = _describe_create_org_unit


# ── زنجیرهٔ ارزیابی (دسترسی ارزیابی) ───────────────────────────────────────


@tool(
    name="get_evaluation_access",
    description="دیدن زنجیرهٔ ارزیابی یک پرسنل: مسئول مستقیم، معاونت، مدیرعامل.",
    category="سازمان",
    read_only=True,
    parameters={"type": "object", "properties": {"personnel_id": {"type": "integer"}}, "required": ["personnel_id"]},
)
def get_evaluation_access(ctx: ToolContext, personnel_id: int) -> ToolOutcome:
    db = ctx.db
    person = _person_or_404(db, personnel_id)
    access = db.scalar(select(EvaluationAccess).where(EvaluationAccess.personnel_id == person.id))
    if access is None:
        return ToolOutcome(
            content=json_content({"personnel_id": person.id, "chain": None, "note": "زنجیره‌ای تعریف نشده است"}),
            summary=f"زنجیرهٔ «{person.full_name}» هنوز تعریف نشده",
        )
    ids = {access.unit_supervisor_user_id, access.deputy_user_id, access.ceo_user_id} - {None}
    names = dict(db.execute(select(User.id, User.username).where(User.id.in_(ids)))) if ids else {}
    payload = {
        "personnel_id": person.id,
        "chain": {
            "unit_supervisor": names.get(access.unit_supervisor_user_id),
            "deputy": names.get(access.deputy_user_id),
            "ceo": names.get(access.ceo_user_id),
        },
    }
    return ToolOutcome(
        content=json_content(payload),
        ui={"kind": "chain_card", "personnel_id": person.id, "chain": payload["chain"]},
        summary=f"زنجیرهٔ ارزیابی «{person.full_name}»",
    )


@tool(
    name="set_evaluation_access",
    description=(
        "تعیین یا اصلاح زنجیرهٔ ارزیابی یک پرسنل (مسئول مستقیم، معاونت، مدیرعامل) با نام کاربری اعضا. قانون‌های تعارض و "
        "خودارزیابی همین‌جا اعمال می‌شود."
    ),
    category="سازمان",
    risky=True,
    capabilities=(Capability.manage_personnel,),
    roles=(UserRole.hr,),
    parameters={
        "type": "object",
        "properties": {
            "personnel_id": {"type": "integer"},
            "unit_supervisor": {"type": "string", "description": "نام کاربری؛ خالی یعنی بدون مسئول مستقیم"},
            "deputy": {"type": "string"},
            "ceo": {"type": "string"},
        },
        "required": ["personnel_id"],
    },
)
def set_evaluation_access(
    ctx: ToolContext,
    personnel_id: int,
    unit_supervisor: str = "",
    deputy: str = "",
    ceo: str = "",
) -> ToolOutcome:
    db = ctx.db
    person = _person_or_404(db, personnel_id)

    def resolve(username: str) -> int | None:
        username = (username or "").strip()
        if not username:
            return None
        user = db.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
        if user is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"کاربر فعالی با نام کاربری «{username}» پیدا نشد",
            )
        return user.id

    sup_id = resolve(unit_supervisor)
    dep_id = resolve(deputy)
    ceo_id = resolve(ceo)
    if person.is_manager:
        sup_id = None
    if ceo_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مدیرعاملِ زنجیره الزامی است")
    if sup_id is None and dep_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "دست‌کم یکی از «مسئول مستقیم» یا «معاونت» لازم است")
    evaluator_ids = [i for i in (sup_id, dep_id, ceo_id) if i is not None]
    ensure_evaluators_are_not_the_subject(db, person.id, evaluator_ids)
    ensure_chain_stages_are_not_redundant(db, sup_id, dep_id, ceo_id)

    access = db.scalar(select(EvaluationAccess).where(EvaluationAccess.personnel_id == person.id))
    before = None
    if access is None:
        access = EvaluationAccess(personnel_id=person.id)
        db.add(access)
    else:
        before = {
            "unit_supervisor_user_id": access.unit_supervisor_user_id,
            "deputy_user_id": access.deputy_user_id,
            "ceo_user_id": access.ceo_user_id,
        }
    access.unit_supervisor_user_id = sup_id
    access.deputy_user_id = dep_id
    access.ceo_user_id = ceo_id
    access.updated_by_user_id = ctx.user.id
    db.flush()

    log_event(
        db,
        actor_user_id=ctx.user.id,
        event_type="evaluation_access_set",
        evaluation_record_id=None,
        old_value=before,
        new_value={
            "personnel_id": person.id,
            "unit_supervisor_user_id": sup_id,
            "deputy_user_id": dep_id,
            "ceo_user_id": ceo_id,
            "via": "ai_copilot",
        },
    )
    db.commit()
    ids = {sup_id, dep_id, ceo_id} - {None}
    names = dict(db.execute(select(User.id, User.username).where(User.id.in_(ids))))
    chain = {
        "unit_supervisor": names.get(sup_id),
        "deputy": names.get(dep_id),
        "ceo": names.get(ceo_id),
    }
    return ToolOutcome(
        content=json_content({"personnel_id": person.id, "chain": chain}),
        ui={"kind": "chain_card", "personnel_id": person.id, "chain": chain},
        summary=f"زنجیرهٔ ارزیابی «{person.full_name}» تعیین شد",
    )


def _describe_set_evaluation_access(personnel_id, unit_supervisor="", deputy="", ceo="", **_):
    parts = []
    if unit_supervisor:
        parts.append(f"مسئول مستقیم {unit_supervisor}")
    if deputy:
        parts.append(f"معاونت {deputy}")
    if ceo:
        parts.append(f"مدیرعامل {ceo}")
    return f"تعیین زنجیرهٔ پرسنل #{personnel_id}" + (" (" + "، ".join(parts) + ")" if parts else "")


set_evaluation_access.describe = _describe_set_evaluation_access


# ── مجوزها ─────────────────────────────────────────────────────────────────


@tool(
    name="list_user_capabilities",
    description="دیدن مجوزهای اداری هر حساب کاربری.",
    category="مدیریت سامانه",
    read_only=True,
    capabilities=(Capability.manage_capabilities,),
    parameters={"type": "object", "properties": {"user_id": {"type": "integer"}}, "required": ["user_id"]},
)
def list_user_capabilities(ctx: ToolContext, user_id: int) -> ToolOutcome:
    db = ctx.db
    account = db.get(User, int(user_id))
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حسابی با این شناسه پیدا نشد")
    from app.services.authorization import capabilities_of

    caps = sorted(c.value for c in capabilities_of(db, account.id))
    return ToolOutcome(
        content=json_content({"user_id": account.id, "username": account.username, "capabilities": caps}),
        summary=f"مجوزهای «{account.username}»",
    )


@tool(
    name="grant_capabilities",
    description="جایگزینی کامل مجوزهای اداری یک حساب. کنشِ حساس: مبنای تفکیک وظایف است.",
    category="مدیریت سامانه",
    risky=True,
    capabilities=(Capability.manage_capabilities,),
    parameters={
        "type": "object",
        "properties": {
            "user_id": {"type": "integer"},
            "capabilities": {
                "type": "array",
                "items": {"type": "string", "enum": [c.value for c in Capability]},
                "description": "فهرست کاملِ مجوزهای تازه — قبلی‌ها جایگزین می‌شوند",
            },
        },
        "required": ["user_id", "capabilities"],
    },
)
def grant_capabilities(ctx: ToolContext, user_id: int, capabilities: list) -> ToolOutcome:
    db = ctx.db
    account = db.get(User, int(user_id))
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حسابی با این شناسه پیدا نشد")
    from app.models.capability import UserCapability
    from app.services.authorization import capabilities_of

    before = sorted(c.value for c in capabilities_of(db, account.id))
    after = []
    for item in capabilities:
        try:
            after.append(Capability(str(item).strip()))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"مجوز شناخته‌نشده: {item}") from None
    db.query(UserCapability).filter(UserCapability.user_id == account.id).delete()
    for cap in set(after):
        db.add(UserCapability(user_id=account.id, capability=cap, granted_by_user_id=ctx.user.id))
    db.flush()
    log_event(
        db,
        actor_user_id=ctx.user.id,
        event_type="capabilities_changed",
        old_value={"user_id": account.id, "capabilities": before},
        new_value={"user_id": account.id, "capabilities": sorted(c.value for c in set(after)), "via": "ai_copilot"},
    )
    db.commit()
    return ToolOutcome(
        content=json_content(
            {"user_id": account.id, "username": account.username, "capabilities": sorted(c.value for c in set(after))}
        ),
        summary=f"مجوزهای «{account.username}» به‌روز شد",
    )


def _describe_grant(user_id, capabilities, **_):
    return f"تنظیم مجوزهای حساب #{user_id} به {len(capabilities)} مجوز"


grant_capabilities.describe = _describe_grant


def _parse_date(value: object) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # شمسی هم پذیرفته می‌شود — همان قاعدهٔ ورود اکسل.
    from app.services.personnel_import import parse_flexible_date

    return parse_flexible_date(text)
