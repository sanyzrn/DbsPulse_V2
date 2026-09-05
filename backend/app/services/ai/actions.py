"""لایهٔ ۴ — کنش‌ها: تجزیه، اعتبارسنجی، تأیید، اجرا.

مدل *پیشنهاد* می‌دهد، کاربر *تصمیم* می‌گیرد. هیچ کنشی بدون فشردنِ دکمه اجرا
نمی‌شود، و این قابل مذاکره نیست: مدلی که «کدام نمره را برای احمدی ثبت کردم؟» را
«پروندهٔ احمدی را حذف کن» بفهمد، روی سرویس‌های ارزان یک فرض دور از ذهن نیست، و
عذرخواهیِ بعدش ردیفِ حذف‌شده را برنمی‌گرداند.

مجوز در *مجری* بررسی می‌شود، نه در پرامپت. پرامپت یک پیشنهاد است؛ کنشی که کاربر
از راه رابط نمی‌توانست انجام دهد، از این‌جا هم نباید بتواند.

چه کنش‌هایی هست و چرا همین‌ها
------------------------------
«ثبت نمره» عمداً نیست. نمره‌دهی در این سامانه یعنی امتیازِ هر شاخص با وزن و
شواهد و مرحلهٔ گردش‌کار؛ یک جملهٔ چت آن را نیمه‌کاره می‌سازد و نیمه‌کاره‌اش بدتر
از نبودنش است. فرمِ نمره‌دهی جای آن کار است.
"""
import json
import re
from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.enums import Capability, PersonnelStatus, UserRole
from app.models.evaluation import EvaluationRecord
from app.models.org_unit import OrgUnit
from app.models.personnel import Personnel
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.services.audit import log_event

#: بلوکِ کنش را «آزادانه» پیدا می‌کنیم. مدل‌ها مقدمه می‌نویسند، برچسب را
#: `json` می‌زنند، حروف بزرگ می‌گذارند یا فاصلهٔ اضافه دارند. سخت‌گیری این‌جا
#: یعنی قابلیت تقریباً نیمی از وقت‌ها شکسته به نظر برسد.
_FENCE = re.compile(r"```[ \t]*(?:pulse|json)?[ \t]*\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class Action:
    name: str
    payload: dict
    #: جمله‌ای که زیرِ دکمهٔ تأیید نوشته می‌شود — به نام، نه به شناسه.
    summary: str
    #: خواندنی است؟ خواندنی‌ها بدون تأیید اجرا می‌شوند چون چیزی عوض نمی‌کنند.
    read_only: bool = False


#: نامِ کنش → (مجوزهای لازم، نقش‌های مجاز). فهرست‌های تهی یعنی «برای همه».
REQUIREMENTS: dict[str, tuple[set[Capability], set[UserRole]]] = {
    "find": (set(), set()),
    "create_personnel": ({Capability.manage_personnel}, {UserRole.hr}),
    "update_personnel": ({Capability.manage_personnel}, {UserRole.hr}),
    "create_org_unit": ({Capability.manage_personnel}, {UserRole.hr}),
    "invite_self_assessment": ({Capability.manage_personnel}, {UserRole.hr}),
    "deactivate_user": ({Capability.manage_users}, set()),
}

ACTION_NAMES = frozenset(REQUIREMENTS)


def allowed_actions(user: CurrentUser, caps: set[Capability]) -> list[str]:
    """کنش‌هایی که *این* کاربر واقعاً می‌تواند اجرا کند.

    همین فهرست به پرامپت می‌رود: تبلیغِ کنشی که کاربر اجازه‌اش را ندارد، یک
    پیشنهادِ مطمئن و یک دکمهٔ مرده تولید می‌کند.
    """
    names = []
    for name, (needed_caps, roles) in REQUIREMENTS.items():
        if not needed_caps and not roles:
            names.append(name)
        elif (needed_caps & caps) or (user.role in roles):
            names.append(name)
    return names


def _clip(value: object, limit: int = 120) -> str:
    return str(value or "").strip()[:limit]


def parse(reply: str) -> list[Action]:
    """هر بلوکِ معتبر یک کنش. هرچه اعتبارسنجی نشود، «هیچ کنشی» است — نه خطا.

    بدنهٔ بدونِ حصار هم پذیرفته می‌شود: مدل‌ها بعد از چند پیام حصار را جا
    می‌اندازند، و بدون این پذیرش قابلیت چند پیام اول کار می‌کند و بعد بی‌صدا
    می‌ایستد.
    """
    bodies = [m.group(1) for m in _FENCE.finditer(reply or "")]
    if not bodies:
        stripped = (reply or "").strip()
        if stripped.startswith("{") or stripped.startswith("["):
            bodies = [stripped]

    actions: list[Action] = []
    for body in bodies:
        try:
            parsed = json.loads(body)
        except ValueError:
            continue
        # یک آرایه هم پذیرفته می‌شود: «این دو را ثبت کن و آن یکی را بردار» سه
        # کنش است و یک خواسته.
        for item in parsed if isinstance(parsed, list) else [parsed]:
            action = _validate(item)
            if action is not None:
                actions.append(action)
    return actions


def strip_action_blocks(reply: str) -> str:
    """آنچه کاربر می‌خواند: نثرِ مدل، بدون بلوک‌های کنش.

    کاربر نباید JSON ببیند. کنش‌ها به‌شکلِ یک *جمله* و یک دکمه نشان داده
    می‌شوند، و بلوکِ خام فقط نویزی است که پیام را ناخوانا می‌کند.

    این‌جا و نه در رابط: همان متنِ پاک‌شده در تاریخچه هم ذخیره می‌شود، وگرنه
    گفت‌وگوی بازخوانی‌شده پر از JSON می‌شد.
    """
    cleaned = _FENCE.sub("", reply or "").strip()
    if cleaned:
        return cleaned
    # پاسخی که *فقط* بلوک بود — قاعدهٔ پرامپت هم دقیقاً همین را می‌خواهد.
    stripped = (reply or "").strip()
    return "" if stripped.startswith(("{", "[", "```")) else stripped


def _validate(item: object) -> Action | None:
    if not isinstance(item, dict):
        return None
    name = str(item.get("action") or "").strip()
    if name not in ACTION_NAMES:
        return None

    if name == "find":
        query = _clip(item.get("query"), 100)
        if not query:
            return None
        return Action(name, {"query": query}, f"جست‌وجوی «{query}»", read_only=True)

    if name == "create_personnel":
        full_name = _clip(item.get("full_name") or item.get("name"), 200)
        code = _clip(item.get("personnel_code") or item.get("code"), 50)
        unit = _clip(item.get("org_unit") or item.get("unit"), 150)
        job = _clip(item.get("job_title") or item.get("role"), 150)
        if not (full_name and code and unit and job):
            return None
        return Action(
            name,
            {
                "full_name": full_name,
                "personnel_code": code,
                "org_unit": unit,
                "job_title": job,
                "is_manager": bool(item.get("is_manager")),
                "contract_end_date": _clip(item.get("contract_end_date"), 20),
            },
            f"ثبت «{full_name}» با کد {code} در واحد {unit} به‌عنوان {job}",
        )

    if name == "update_personnel":
        pid = _as_id(item.get("id") or item.get("personnel_id"))
        fields = item.get("fields")
        if pid is None or not isinstance(fields, dict) or not fields:
            return None
        allowed = {"job_title", "org_unit", "is_manager", "contract_end_date"}
        clean = {k: fields[k] for k in allowed if k in fields}
        if not clean:
            return None
        return Action(
            name,
            {"id": pid, "fields": clean},
            "به‌روزرسانی پروندهٔ پرسنلی: " + "، ".join(f"{k} = {v}" for k, v in clean.items()),
        )

    if name == "create_org_unit":
        unit_name = _clip(item.get("name"), 150)
        if not unit_name:
            return None
        site = _clip(item.get("site"), 100)
        return Action(
            name,
            {"name": unit_name, "site": site},
            f"افزودن واحد «{unit_name}»" + (f" در محل {site}" if site else ""),
        )

    if name == "invite_self_assessment":
        pid = _as_id(item.get("personnel_id") or item.get("id"))
        if pid is None:
            return None
        return Action(name, {"personnel_id": pid}, "فرستادن دعوت خودارزیابی")

    if name == "deactivate_user":
        uid = _as_id(item.get("user_id") or item.get("id"))
        if uid is None:
            return None
        return Action(name, {"user_id": uid}, "غیرفعال‌کردن حساب کاربری")

    return None


def _as_id(value: object) -> int | None:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


# ── اجرا ──────────────────────────────────────────────────────────────────


def _guard(action: str, user: CurrentUser, caps: set[Capability]) -> None:
    if action not in allowed_actions(user, caps):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما اجازهٔ این کار را ندارید؛ دستیار هم همان محدودیت را دارد.",
        )


def execute(db: Session, action: Action, user: CurrentUser, caps: set[Capability]) -> str:
    """اجرا، با همان گاردی که رابط دارد. خروجی، جمله‌ای برای نمایش به کاربر."""
    _guard(action.name, user, caps)
    handler = {
        "find": _do_find,
        "create_personnel": _do_create_personnel,
        "update_personnel": _do_update_personnel,
        "create_org_unit": _do_create_org_unit,
        "invite_self_assessment": _do_invite,
        "deactivate_user": _do_deactivate_user,
    }[action.name]
    return handler(db, action.payload, user)


def _do_find(db: Session, payload: dict, user: CurrentUser) -> str:
    q = f"%{payload['query']}%"
    people = list(
        db.scalars(
            select(Personnel)
            .where(or_(Personnel.full_name.ilike(q), Personnel.personnel_code.ilike(q)))
            .limit(10)
        )
    )
    records = list(
        db.scalars(select(EvaluationRecord).where(EvaluationRecord.evaluation_code.ilike(q)).limit(5))
    )
    if not people and not records:
        return "چیزی پیدا نشد."
    out = []
    for p in people:
        out.append(f"[{p.id}] {p.full_name} — کد {p.personnel_code} — {p.job_title} — {p.org_unit}")
    for r in records:
        out.append(f"[{r.id}] پرونده {r.evaluation_code} — وضعیت {r.status.value}")
    return "\n".join(out)


def _do_create_personnel(db: Session, payload: dict, user: CurrentUser) -> str:
    if db.scalar(select(Personnel).where(Personnel.personnel_code == payload["personnel_code"])):
        raise HTTPException(400, "این کد پرسنلی از قبل ثبت شده است")
    end = _parse_date(payload.get("contract_end_date")) or date(date.today().year + 1, 1, 1)
    person = Personnel(
        personnel_code=payload["personnel_code"],
        full_name=payload["full_name"],
        job_title=payload["job_title"],
        org_unit=payload["org_unit"],
        is_manager=payload["is_manager"],
        contract_start_date=date.today(),
        contract_end_date=end,
        status=PersonnelStatus.active,
    )
    db.add(person)
    db.flush()
    log_event(
        db,
        actor_user_id=user.id,
        event_type="personnel_created",
        new_value={"id": person.id, "via": "ai_assistant"},
    )
    db.commit()
    return (
        f"«{person.full_name}» ثبت شد (شناسه {person.id}). زنجیرهٔ ارزیابی‌اش هنوز تعیین نشده — "
        "از صفحهٔ پرسنل کاملش کنید."
    )


def _do_update_personnel(db: Session, payload: dict, user: CurrentUser) -> str:
    person = db.get(Personnel, payload["id"])
    if person is None:
        raise HTTPException(404, "پرسنلی با این شناسه پیدا نشد")
    before = {}
    for key, value in payload["fields"].items():
        before[key] = str(getattr(person, key, ""))
        if key == "contract_end_date":
            parsed = _parse_date(value)
            if parsed is None:
                raise HTTPException(400, "تاریخ پایان قرارداد خوانده نشد")
            person.contract_end_date = parsed
        elif key == "is_manager":
            person.is_manager = bool(value)
        else:
            setattr(person, key, str(value)[:150])
    log_event(
        db,
        actor_user_id=user.id,
        event_type="personnel_updated",
        old_value=before,
        new_value={"id": person.id, "via": "ai_assistant", **{k: str(v) for k, v in payload["fields"].items()}},
    )
    db.commit()
    return f"پروندهٔ «{person.full_name}» به‌روز شد."


def _do_create_org_unit(db: Session, payload: dict, user: CurrentUser) -> str:
    unit = OrgUnit(site=payload["site"] or None, name=payload["name"], is_active=True)
    db.add(unit)
    db.flush()
    log_event(
        db,
        actor_user_id=user.id,
        event_type="org_unit_created",
        new_value={"id": unit.id, "full_name": unit.full_name, "via": "ai_assistant"},
    )
    db.commit()
    return f"واحد «{unit.full_name}» افزوده شد."


def _do_invite(db: Session, payload: dict, user: CurrentUser) -> str:
    from app.services.self_assessment import invite

    person = db.get(Personnel, payload["personnel_id"])
    if person is None:
        raise HTTPException(404, "پرسنلی با این شناسه پیدا نشد")
    invite(db, person, user.id)
    db.commit()
    return f"دعوت خودارزیابی برای «{person.full_name}» فرستاده شد."


def _do_deactivate_user(db: Session, payload: dict, user: CurrentUser) -> str:
    account = db.get(User, payload["user_id"])
    if account is None:
        raise HTTPException(404, "حسابی با این شناسه پیدا نشد")
    if account.id == user.id:
        raise HTTPException(400, "نمی‌توانید حساب خودتان را غیرفعال کنید")
    account.is_active = False
    log_event(
        db,
        actor_user_id=user.id,
        event_type="user_deactivated",
        new_value={"user_id": account.id, "via": "ai_assistant"},
    )
    db.commit()
    return f"حساب «{account.username}» غیرفعال شد."


def _parse_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        return None
