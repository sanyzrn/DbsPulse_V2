"""لایهٔ ابزارِ دستیار — هستهٔ ثبت، گارد، و اجرا.

این فایل چیزی دربارهٔ «پرسنل» یا «ارزیابی» نمی‌داند؛ فقط قراردادِ ابزار را
نگه می‌دارد. هر ابزار سه چیز لازم دارد:

* ``name`` و ``description`` و شِمای پارامترها — همان چیزی که به مدل می‌رود؛
* ملاکِ دسترسی: کدام مجوزها/نقش‌ها — همان دروازه‌ای که رابط هم دارد؛
* تابعِ اجرا که از سرویس‌های رسمی سامانه استفاده می‌کند، نه کوئریِ موازی.

دو قاعدهٔ تغییرناپذیر
---------------------
۱. **مجوز در لحظهٔ اجرا سنجیده می‌شود، نه در پرامپت.** آن‌چه به مدل می‌گوید
   «چه ابزارهایی داری» فقط *تبلیغ* است؛ هر اجرا دوباره از ``guard`` می‌گذرد.
   بدنهٔ درخواست از مرورگر می‌آید و مرورگر دست‌کاری‌شدنی است.
۲. **ابزارِ تغییردهنده خودش چیزی را اجرا نمی‌کند.** خروجیِ handler آن یک
   «در انتظارِ تأیید» است؛ اجرا فقط با تصمیم آدم از نقطهٔ تأیید رخ می‌دهد.
"""
from __future__ import annotations

import inspect
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.enums import Capability, UserRole
from app.schemas.auth import CurrentUser

# ── قراردادِ ابزار ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ToolSpec:
    """تعریف یک ابزار — همان چیزی که ثبت می‌شود و به مدل تبلیغ می‌شود."""

    name: str
    description: str
    parameters: dict
    category: str
    handler: Callable[..., "ToolOutcome"]
    #: خواندنی؟ خواندنی‌ها بلافاصله اجرا می‌شوند چون چیزی عوض نمی‌کنند.
    read_only: bool = False
    #: پرخطر؟ اجرایش فقط پس از تأییدِ صریح کاربر ممکن است — حتی اگر مجاز باشد.
    risky: bool = False
    #: مجوزهای لازم. تهی یعنی «با هر مجوزی» — اما نه لزوماً برای هر نقشی.
    capabilities: frozenset[Capability] = frozenset()
    #: نقش‌های مجاز. تهی یعنی «هر نقشی که مجوزهایش را دارد».
    roles: frozenset[UserRole] = frozenset()

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def summary_of(self, arguments: dict) -> str:
        """جمله‌ای که زیر کارتِ تأیید می‌نشیند.

        خودِ ابزار بهتر از هرکس می‌داند کارش را با چه جمله‌ای توصیف کند؛
        handler می‌تواند تابعِ ``describe`` داشته باشد. اگر نبود، نامِ ابزار
        و آرگومان‌ها می‌آید.
        """
        describe = getattr(self.handler, "describe", None)
        if describe is not None:
            try:
                return str(describe(**_clean_kwargs(describe, arguments)))
            except Exception:  # noqa: BLE001 — جملهٔ بد نباید اجرا را ببندد
                pass
        args = "، ".join(f"{k}={v}" for k, v in arguments.items())
        return f"{self.name}({args})"


@dataclass
class ToolOutcome:
    """خروجی ابزار — هم برای مدل، هم برای رابط.

    ``content`` متنِ خامی است که مدل می‌بیند (JSON-خوانا). ``ui`` اختیاری است:
    یک payload ساخت‌یافته که کارتِ رابط نمایش می‌دهد، تا جدولِ ۳۰ ردیفی به‌شکل
    نثرِ طولانی خوانده نشود. ``summary`` جملهٔ کوتاهِ ردِ کاری که در «گام‌های
    این نوبت» نشان داده می‌شود.
    """

    content: str
    ui: dict = field(default_factory=dict)
    summary: str = ""


@dataclass(frozen=True)
class ToolContext:
    """همهٔ آنچه اجرای یک ابزار لازم دارد — و چیزی بیش از آن."""

    db: Session
    user: CurrentUser
    caps: frozenset[Capability]
    conversation_id: int
    #: سوییچِ اصلیِ نوشتنِ دستیار (تنظیمات + دسترسیِ کاربر). فقط برای *تبلیغ*
    #: نیست؛ execute_tool در لحظهٔ اجرا هم آن را سنجد تا ابزاری که به هر
    #: شکلی (بلوکِ JSON، ابزارِ تبلیغ‌نشده، ابزارِ تازه) صدا زده شد نتواند
    #: سوییچِ خاموش را دور بزند.
    allow_writes: bool = True


# ── ثبت ────────────────────────────────────────────────────────────────────

REGISTRY: dict[str, ToolSpec] = {}


def tool(
    *,
    name: str,
    description: str,
    parameters: dict,
    category: str,
    read_only: bool = False,
    risky: bool = False,
    capabilities: tuple = (),
    roles: tuple = (),
) -> Callable:
    """دکوراتورِ ثبت ابزار. هر ابزار دقیقاً یک‌بار ثبت می‌شود."""

    def register(fn: Callable) -> Callable:
        if name in REGISTRY:
            raise ValueError(f"ابزار تکراری: {name}")
        REGISTRY[name] = ToolSpec(
            name=name,
            description=description,
            parameters=parameters,
            category=category,
            handler=fn,
            read_only=read_only,
            risky=risky,
            capabilities=frozenset(capabilities),
            roles=frozenset(roles),
        )
        return fn

    return register


def _clean_kwargs(fn: Callable, arguments: dict) -> dict:
    """آرگومان‌هایی که امضای تابع واقعاً می‌پذیرد.

    مدل گاهی کلیدِ اضافه می‌فرستد؛ بی‌سکوتِ این‌جا یعنی TypeError به‌جای
    پیامِ درست.
    """
    params = inspect.signature(fn).parameters
    accepted = {
        name for name, param in params.items()
        if param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY)
    }
    return {k: v for k, v in arguments.items() if k in accepted}


def get_tool(name: str) -> ToolSpec | None:
    return REGISTRY.get((name or "").strip())


# ── گارد ───────────────────────────────────────────────────────────────────


def is_allowed(spec: ToolSpec, user: CurrentUser, caps: set[Capability]) -> bool:
    """همان معادله‌ای که کنش‌های نسخهٔ قبل داشتند، حالا برای همهٔ ابزارها.

    مجوزِ متناسب موجود باشد *یا* نقشِ کاربر یکی از نقش‌های صریح ابزار — و اگر
    ابزار هیچ‌کدام را نسنجیده باشد، برای همه است.
    """
    if not spec.capabilities and not spec.roles:
        return True
    if spec.capabilities and (set(spec.capabilities) & set(caps)):
        return True
    if spec.roles and user.role in spec.roles:
        return True
    return False


def guard(spec: ToolSpec, user: CurrentUser, caps: set[Capability]) -> None:
    if not is_allowed(spec, user, caps):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما اجازهٔ این کار را ندارید؛ دستیار هم همان محدودیت را دارد.",
        )


def allowed_tools(
    user: CurrentUser, caps: set[Capability], *, allow_writes: bool
) -> list[ToolSpec]:
    """ابزارهایی که به *این* کاربر تبلیغ می‌شود — نه بیشتر.

    تبلیغِ ابزاری که اجرا نمی‌شود = پیشنهادِ مطمئن با دکمهٔ مرده.
    """
    out = []
    for spec in REGISTRY.values():
        if not allow_writes and not spec.read_only:
            continue
        if is_allowed(spec, user, caps):
            out.append(spec)
    return out


# ── شِمای OpenAI و پروتکلِ جایگزین ─────────────────────────────────────────


def openai_tools_schema(specs: list[ToolSpec]) -> list[dict]:
    return [spec.to_openai_schema() for spec in specs]


_FENCE = re.compile(r"```[ \t]*(?:pulse|json|tool)?[ \t]*\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)


def parse_fallback_blocks(reply: str) -> list[tuple[str, dict]]:
    """پروتکلِ جایگزین برای سرویس‌هایی که فراخوانیِ ابزار بومی ندارند.

    مدل به‌جای tool_call، بلوکِ JSON می‌نویسد. سه شکل پذیرفته می‌شود:
    ``{"tool": name, "arguments": {...}}`` (شکلِ رسمی)،
    ``{"tool": name, ...کلیدها}``، و ``{"action": name, ...کلیدها}``
    (سازگار با پرامپت‌هایی که مدل از حفظ است).
    """
    bodies = [m.group(1) for m in _FENCE.finditer(reply or "")]
    if not bodies:
        stripped = (reply or "").strip()
        if stripped.startswith("{") or stripped.startswith("["):
            bodies = [stripped]

    calls: list[tuple[str, dict]] = []
    for body in bodies:
        try:
            parsed = json.loads(body)
        except ValueError:
            continue
        items = parsed if isinstance(parsed, list) else [parsed]
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("tool") or item.get("action") or "").strip()
            if not name:
                continue
            arguments = item.get("arguments") or item.get("payload")
            if not isinstance(arguments, dict):
                arguments = {
                    k: v for k, v in item.items()
                    if k not in ("tool", "action", "arguments", "payload")
                }
            calls.append((name, arguments))
    return calls


def strip_fallback_blocks(reply: str) -> str:
    cleaned = _FENCE.sub("", reply or "").strip()
    if cleaned:
        return cleaned
    stripped = (reply or "").strip()
    return "" if stripped.startswith(("{", "[", "```")) else stripped


# ── اجرا ───────────────────────────────────────────────────────────────────

#: کلیدهایی که هرگز در لاگِ ممیزی نمی‌نشینند — در هیچ عمقی.
_SENSITIVE_KEYS = {"password", "initial_password", "api_key", "new_password", "current_password", "temporary_password"}
#: برچسبِ ستونِ رمز در قالبِ رسمیِ ورود پرسنل و نام‌های رایج فارسیِ رمز —
#: مقادیر این کلیدها وقتی آرگومانِ ابزارند (مثلاً در editsِ اکسل) هم محرمانه‌اند.
_SENSITIVE_KEYS |= {"رمز اولیه", "رمز عبور", "گذرواژه"}


def _sanitize_value(value):
    """پاک‌سازیِ بازگشتی: راز در هر عمقی ماسک می‌شود، نه فقط در سطحِ اول.

    پیش از این فقط کلیدهای سطحِ بالا سنجیده می‌شدند؛ آرگومانِ «لیستِ ویرایش‌ها»
    یا هر آبجکتِ تو در تو، رمزِ داخلش را بی‌صدا به لاگِ ممیزیِ زنجیره‌دار
    می‌فرستاد (M-8 در گزارش ممیزی).
    """
    if isinstance(value, dict):
        return {
            k: ("***" if k in _SENSITIVE_KEYS else _sanitize_value(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(item) for item in value]
    return value


def sanitize_arguments(arguments: dict) -> dict:
    return _sanitize_value(arguments)


def execute_tool(ctx: ToolContext, spec: ToolSpec, arguments: dict) -> ToolOutcome:
    """اجرا با گاردِ کامل و لاگِ ممیزی.

    تراکنش: این‌جا commit نمی‌شود — همان قراردادِ کل سامانه (سرویس‌ها flush
    می‌کنند، فراخواننده commit می‌کند). فراخواننده این تابع یعنی حلقهٔ گفت‌وگو
    یا نقطهٔ تأیید.
    """
    guard(spec, ctx.user, ctx.caps)
    # سوییچِ نوشتن، در لحظهٔ اجرا — مستقل از تبلیغ. تبلیغ فقط فهرستِ پیشنهادی
    # است؛ مدل می‌تواند نامِ ابزاری را صدا بزند که به او نشان داده نشده. (H-1)
    if not spec.read_only and not ctx.allow_writes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="اجازهٔ تغییر داده ندارید؛ دستیار شما در حالت فقط-خواندنی است.",
        )

    from app.services.audit import log_event

    try:
        outcome = spec.handler(ctx, **_clean_kwargs(spec.handler, arguments))
    except HTTPException:
        # نوشته‌های ناقصِ همین ابزار باید دور ریخته شود — نه اینکه لاگِ شکست
        # نیمه‌کاره‌ها را *کامیت* کند (H-3). لاگ در تراکنشِ تمیزِ بعدی می‌نشیند.
        ctx.db.rollback()
        log_event(
            ctx.db,
            actor_user_id=ctx.user.id,
            event_type="ai_tool_failed",
            new_value={
                "tool": spec.name,
                "arguments": sanitize_arguments(arguments),
                "conversation_id": ctx.conversation_id,
                "via": "ai_copilot",
            },
        )
        ctx.db.commit()
        raise
    except Exception as exc:  # noqa: BLE001 — خطای خام ابزار، خطای ممیزی‌پذیر می‌شود
        ctx.db.rollback()
        log_event(
            ctx.db,
            actor_user_id=ctx.user.id,
            event_type="ai_tool_failed",
            new_value={
                "tool": spec.name,
                "arguments": sanitize_arguments(arguments),
                "conversation_id": ctx.conversation_id,
                "error": str(exc)[:300],
                "via": "ai_copilot",
            },
        )
        ctx.db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="اجرای این کار در سامانه شکست خورد. جزئیات در گزارش رویدادها ثبت شد.",
        ) from exc

    log_event(
        ctx.db,
        actor_user_id=ctx.user.id,
        event_type="ai_tool_invoked",
        new_value={
            "tool": spec.name,
            "arguments": sanitize_arguments(arguments),
            "conversation_id": ctx.conversation_id,
            "read_only": spec.read_only,
            "via": "ai_copilot",
        },
    )
    return outcome


def json_content(payload: Any) -> str:
    """محتوایی که مدل می‌بیند — JSON خوانا، کوتاه، بدون کلید اضافه."""
    return json.dumps(payload, ensure_ascii=False, default=str)
