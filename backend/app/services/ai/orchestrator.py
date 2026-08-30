"""حلقهٔ گفت‌وگوی همکار: از «پرسش» تا «انجام‌شده» در چند پله.

یک نوبتِ گفت‌وگو ممکن است چند ابزار بخواهد: جست‌وجو، خواندن جزئیات، و در
انتها ساختنِ یک پیشنهادِ تغییر. این ماژول آن حلقه را می‌چرخاند — با دو سقفِ
سخت: عمقِ حلقه از تنظیمات می‌آید و هر ابزار پیش از اجرا از گاردِ همان
کاربر می‌گذرد.

دو پروتکل:
* **بومی** — سرویسِ سازگار با OpenAI که `tools` را می‌پذیرد؛ خواستهٔ ابزار در
  `tool_calls` می‌آید.
* **جایگزین** — سرویسی که شِمای ابزار را نمی‌شناسد؛ مدل بلوکِ `pulse` می‌نویسد
  و همین‌جا تجزیه می‌شود. انتخابِ پروتکل خودکار است: اول بومی امتحان می‌شود،
  و اگر سرویس صراحتاً رد کرد، تا انتهای نوبت جایگزین می‌ماند.

کنش‌های پرخطر در این حلقه *اجرا* نمی‌شوند؛ «در انتظارِ تأیید» ساخته می‌شوند و
اجرایشان فقط از نقطهٔ تأیید ممکن است.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import AiConversation, AiMessage, AiPendingAction, AiSettings
from app.models.enums import Capability
from app.schemas.auth import CurrentUser
from app.services.ai import context as context_service
from app.services.ai.port import ChatMessage, ChatResponse, ToolCall, ToolProtocolUnsupported
from app.services.ai.prompt import build_system_prompt
from app.services.ai.tools import base as tools_base
from app.services.ai.tools.base import ToolContext, ToolSpec, execute_tool, json_content
from app.services.audit import log_event
from app.services.authorization import capabilities_of


@dataclass
class StepTrace:
    """ردِ یک فراخوانیِ ابزار برای نمایش در رابط — «دستیار چه کرد»."""

    tool: str
    status: str  # ok | awaiting_confirmation | error
    summary: str = ""
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"tool": self.tool, "status": self.status, "summary": self.summary, "detail": self.detail}


@dataclass
class TurnResult:
    conversation_id: int
    reply: str
    steps: list[StepTrace] = field(default_factory=list)
    pending: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)

    def meta_json(self) -> str:
        return json.dumps(
            {
                "steps": [s.to_dict() for s in self.steps],
                "pending": self.pending,
            },
            ensure_ascii=False,
        )


def _pending_dict(row: AiPendingAction) -> dict:
    return {
        "id": row.id,
        "tool": row.tool_name,
        "summary": row.summary,
        "arguments": json.loads(row.arguments_json or "{}"),
        "expires_at": row.expires_at.isoformat(),
    }


def _attachments_note(db: Session, conversation_id: int) -> str:
    """معرفیِ پیوست‌های اخیرِ گفت‌وگو به مدل — با شناسه، تا بتواند به آن‌ها ارجاع بدهد."""
    from app.models.ai import AiUpload

    rows = list(
        db.scalars(
            select(AiUpload)
            .where(AiUpload.conversation_id == conversation_id)
            .order_by(AiUpload.id.desc())
            .limit(3)
        )
    )[::-1]
    if not rows:
        return ""
    lines = []
    for upload in rows:
        try:
            parsed = json.loads(upload.structure_json or "{}")
        except ValueError:
            parsed = {}
        kind = parsed.get("kind", "file")
        if kind == "personnel_import":
            lines.append(
                f"- فایل #{upload.id} «{upload.filename}» — اکسل پرسنلِ مرحله‌بندی‌شده "
                f"(commit شده: {'بله' if parsed.get('committed') else 'خالی'})"
            )
        elif kind == "excel":
            lines.append(f"- فایل #{upload.id} «{upload.filename}» — اکسلِ غیرِ قالبِ پرسنل")
        else:
            lines.append(f"- فایل #{upload.id} «{upload.filename}» — بدون قالبِ قابل پردازش")
    return "\n".join(lines)


def _history_messages(
    db: Session, conversation_id: int, exclude_id: int | None = None, limit: int = 12
) -> list[ChatMessage]:
    stmt = select(AiMessage).where(AiMessage.conversation_id == conversation_id)
    if exclude_id is not None:
        stmt = stmt.where(AiMessage.id != exclude_id)
    rows = list(
        db.scalars(
            stmt.order_by(AiMessage.id.desc()).limit(limit)
        )
    )[::-1]
    return [ChatMessage(role=row.role, content=row.content) for row in rows if row.role in ("user", "assistant")]


def _system_prompt(
    *,
    db: Session,
    config: AiSettings,
    user: CurrentUser,
    caps: set[Capability],
    allow_writes: bool,
    specs: list[ToolSpec],
    fallback_protocol: bool,
    conversation_id: int,
) -> str:
    return build_system_prompt(
        instructions=config.instructions or "",
        context=context_service.build(db, user, caps, config.context_record_limit),
        user=user,
        caps=caps,
        allow_writes=allow_writes,
        restrict_to_platform=config.restrict_to_platform,
        tools=specs,
        fallback_protocol=fallback_protocol,
        attachments_note=_attachments_note(db, conversation_id),
    )


def _execute_call(
    ctx: ToolContext,
    spec: ToolSpec,
    arguments: dict,
    *,
    allow_writes: bool,
    steps: list[StepTrace],
    created_pending: list[dict],
) -> str:
    """اجرای یک خواستهٔ ابزار — پرخطرها اجرا نمی‌شوند، پیشنهاد می‌شوند.

    خروجی، متنِ نتیجه برای زدن به مدل است (پیامِ role="tool").
    """
    db = ctx.db
    if spec.risky:
        if not allow_writes:
            return json_content({"error": "اجازهٔ تغییر داده ندارید؛ این کنش فقط خواندنی است."})
        tools_base.guard(spec, ctx.user, ctx.caps)
        pending = AiPendingAction(
            conversation_id=ctx.conversation_id,
            user_id=ctx.user.id,
            tool_name=spec.name,
            arguments_json=json.dumps(arguments, ensure_ascii=False, default=str),
            summary=spec.summary_of(arguments),
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(hours=tools_uploads_ttl()),
        )
        db.add(pending)
        db.flush()
        created_pending.append(_pending_dict(pending))
        steps.append(
            StepTrace(
                tool=spec.name,
                status="awaiting_confirmation",
                summary=pending.summary,
                detail={"pending_action_id": pending.id},
            )
        )
        return json_content({
            "status": "awaiting_confirmation",
            "pending_action_id": pending.id,
            "summary": pending.summary,
            "note": (
                "این کنش اجرا نشده است. کاربر باید کارتِ تأیید را بپذیرد یا رد کند؛"
                " تو در این باره توضیح بده و منتظر بمان."
            ),
        })

    outcome = execute_tool(ctx, spec, arguments)
    steps.append(
        StepTrace(
            tool=spec.name,
            status="ok",
            summary=outcome.summary or spec.summary_of(arguments),
            detail=outcome.ui if outcome.ui else {},
        )
    )
    return outcome.content


def tools_uploads_ttl() -> int:
    from app.services.ai.tools.uploads import PENDING_TTL_HOURS

    return PENDING_TTL_HOURS


def _parse_arguments(raw: str) -> dict:
    try:
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except ValueError:
        return {}


async def run_turn(
    db: Session,
    *,
    user: CurrentUser,
    conversation: AiConversation,
    config: AiSettings,
    api_key: str,
    access_model: str,
    adapter_factory,
    user_text: str,
    allow_writes: bool,
    user_message_id: int | None = None,
) -> TurnResult:
    """یک نوبت کامل. `adapter_factory` تنها برای تست تزریق می‌شود."""
    caps = set(capabilities_of(db, user.id))
    specs = tools_base.allowed_tools(user, caps, allow_writes=allow_writes)
    ctx = ToolContext(
        db=db, user=user, caps=frozenset(caps), conversation_id=conversation.id, allow_writes=allow_writes
    )

    messages: list[ChatMessage] = []
    fallback_mode = False
    steps: list[StepTrace] = []
    created_pending: list[dict] = []
    usage: dict = {}
    reply = ""

    max_iterations = max(1, int(config.max_tool_iterations or 6))

    for iteration in range(max_iterations):
        if not messages:
            messages = [ChatMessage("system", _system_prompt(
                db=db,
                config=config,
                user=user,
                caps=caps,
                allow_writes=allow_writes,
                specs=specs,
                fallback_protocol=False,
                conversation_id=conversation.id,
            ))]
            messages += _history_messages(db, conversation.id, exclude_id=user_message_id)
            messages.append(ChatMessage("user", user_text))
        # پلهٔ آخر بدون ابزار: مدلِ حرف‌نزن‌گرده وادار به جمع‌بندی می‌شود.
        force_text = iteration == max_iterations - 1
        wire_specs = tools_base.openai_tools_schema(specs) if (specs and not force_text and not fallback_mode) else None

        adapter = adapter_factory()
        try:
            if wire_specs:
                response: ChatResponse = await adapter.send(messages, tools=wire_specs)
            else:
                response = await adapter.send(messages)
        except ToolProtocolUnsupported:
            # سرویس شِمای ابزار را نمی‌شناسد؛ از نو با پروتکلِ JSON می‌رویم.
            fallback_mode = True
            messages[0] = ChatMessage("system", _system_prompt(
                db=db,
                config=config,
                user=user,
                caps=caps,
                allow_writes=allow_writes,
                specs=specs,
                fallback_protocol=True,
                conversation_id=conversation.id,
            ))
            adapter = adapter_factory()
            response = await adapter.send(messages)

        usage = response.usage or usage

        # منبعِ خواسته‌های ابزار: بومی = tool_calls؛ جایگزین = بلوک‌های JSON
        # که به همان شکلِ ToolCall نرمال می‌شوند تا حلقه یکسان بماند.
        if not fallback_mode:
            calls = list(response.tool_calls)
        else:
            calls = [
                ToolCall(
                    id=f"fb_{index}",
                    name=name,
                    arguments_json=json.dumps(arguments, ensure_ascii=False, default=str),
                )
                for index, (name, arguments) in enumerate(tools_base.parse_fallback_blocks(response.content))
            ]

        if not calls:
            reply = (
                tools_base.strip_fallback_blocks(response.content)
                if fallback_mode
                else response.content
            ).strip()
            break

        if fallback_mode:
            visible = tools_base.strip_fallback_blocks(response.content).strip()
            if visible:
                messages.append(ChatMessage("assistant", visible))
        else:
            messages.append(
                ChatMessage(
                    "assistant",
                    response.content or "",
                    tool_calls=tuple(
                        ToolCall(id=c.id, name=c.name, arguments_json=c.arguments_json)
                        for c in calls
                    ),
                )
            )

        for call in calls:
            spec = tools_base.get_tool(call.name)
            if spec is None:
                messages.append(
                    ChatMessage(
                        "tool",
                        json_content({"error": f"ابزاری به نام «{call.name}» وجود ندارد"}),
                        tool_call_id=call.id,
                    )
                )
                steps.append(StepTrace(tool=call.name, status="error", summary="ابزار شناخته نشد"))
                continue
            arguments = _parse_arguments(call.arguments_json)
            if not fallback_mode and not call.id:
                call = ToolCall(id="call_0", name=call.name, arguments_json=call.arguments_json)
            try:
                result_text = _execute_call(
                    ctx, spec, arguments, allow_writes=allow_writes, steps=steps, created_pending=created_pending
                )
            except HTTPException as err:
                result_text = json_content({"error": err.detail})
                steps.append(
                    StepTrace(
                        tool=spec.name,
                        status="error",
                        summary=str(err.detail),
                        detail={"status": err.status_code},
                    )
                )
            messages.append(ChatMessage("tool", result_text, tool_call_id=call.id))
            # هر پله سالم ماندگار می‌شود؛ شکستِ پلهٔ بعد پیشین‌ها را نمی‌بَرد.
            # کامیتِ نوبت‌به‌نوبتِ قبلی یعنی پله‌های همین دورِ حلقه تا آخرِ آن
            # نیمه‌کاره می‌ماندند و rollbackِ شکستِ یک ابزار، پیشنهادِ در-انتظارِ
            # تأییدِ همان دور را هم می‌بُرد (H-3).
            db.commit()

    if not reply:
        reply = (
            "کاری که خواستید چند پله پیش رفت؛ برای ادامه از من بخواهید دوباره پیگیری کنم. "
            "اگر پیشنهادی در انتظار تأیید است، کارتش را در همین گفت‌وگو می‌بینید."
        )

    # کنش‌های در انتظارِ تأییدِ *همین نوبت* فقط وقتی معتبرند که مالکشان تصمیم نگرفته باشد
    live_pending = [
        p for p in created_pending
        if db.scalar(
            select(AiPendingAction).where(
                AiPendingAction.id == p["id"], AiPendingAction.status == "pending"
            )
        )
        is not None
    ]

    return TurnResult(
        conversation_id=conversation.id,
        reply=reply,
        steps=steps,
        pending=live_pending,
        usage=usage,
    )


def log_turn_error(db: Session, user: CurrentUser, conversation_id: int, detail: str) -> None:
    log_event(
        db,
        actor_user_id=user.id,
        event_type="ai_turn_failed",
        new_value={"conversation_id": conversation_id, "detail": detail[:300], "via": "ai_copilot"},
    )
