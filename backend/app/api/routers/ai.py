"""دستیار هوشمند — گفت‌وگو، کنش‌ها، و تنظیماتش.

دو دستهٔ کاملاً جدا در یک فایل:

* `/api/ai/chat`, `/status`, `/conversations`, `/run-action` — برای *کاربرِ*
  دستیار. معاونتی که فقط باید بپرسد، همین‌ها را می‌بیند و بس.
* `/api/ai/settings`, `/access` — پشتِ `manage_ai`. کلید API، متنِ راهنما،
  اینکه چه کسی دستیار دارد.

جداکردنشان در سطح مجوز است و نه در سطح رابط: پنهان‌کردنِ یک دکمه در فرانت‌اند
تنظیمات را محافظت نمی‌کند.
"""
import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_capability
from app.core.crypto import decrypt, encrypt, masked
from app.db.session import get_db
from app.models.ai import (
    DEFAULT_INSTRUCTIONS,
    AiConversation,
    AiMessage,
    AiSettings,
    AiUserAccess,
)
from app.models.enums import Capability
from app.models.user import User
from app.schemas.ai import (
    AiActionRead,
    AiChatRequest,
    AiChatResponse,
    AiConversationRead,
    AiMessageRead,
    AiRunActionRequest,
    AiRunActionResponse,
    AiSettingsRead,
    AiSettingsUpdate,
    AiStatus,
    AiTestRequest,
    AiTestResult,
    AiUserAccessRead,
    AiUserAccessUpdate,
)
from app.schemas.auth import CurrentUser
from app.services.ai import actions as action_service
from app.services.ai import context as context_service
from app.services.ai.port import AiRequestFailed, AiUnavailable, ChatMessage
from app.services.ai.prompt import build_system_prompt
from app.services.ai.provider import OpenAiCompatibleAdapter
from app.services.audit import log_event
from app.services.authorization import capabilities_of

router = APIRouter(prefix="/api/ai", tags=["ai"])

_admin = require_capability(Capability.manage_ai)

#: چند پیامِ اخیر همراه پرسش می‌رود. کوتاه عمدی است: تاریخچهٔ بلند هزینه است و
#: مدل‌های ارزان با آن بدتر جواب می‌دهند، نه بهتر.
_HISTORY_TURNS = 12


def _settings_row(db: Session) -> AiSettings:
    row = db.get(AiSettings, 1)
    if row is None:
        row = AiSettings(id=1, instructions=DEFAULT_INSTRUCTIONS)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _access_row(db: Session, user_id: int) -> AiUserAccess | None:
    return db.scalar(select(AiUserAccess).where(AiUserAccess.user_id == user_id))


def _resolve(db: Session, user: CurrentUser) -> tuple[AiSettings, AiUserAccess, str]:
    """تنظیمات مؤثر برای همین کاربر، یا یک خطای *قابل اقدام*.

    سه حالت جدا نگه داشته می‌شوند چون در کد یکی به‌نظر می‌رسند و برای کاربر
    کاملاً فرق دارند: «راه‌اندازی نشده»، «برای شما روشن نیست»، «کلید ندارد».
    """
    config = _settings_row(db)
    if not config.enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دستیار هوشمند در این سامانه فعال نیست")

    access = _access_row(db, user.id)
    if access is None or not access.enabled:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "دستیار هوشمند برای حساب شما فعال نشده است. از مدیر سامانه بخواهید فعالش کند.",
        )

    api_key = decrypt(access.api_key_encrypted) or decrypt(config.api_key_encrypted)
    if not api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "کلید سرویس هوش مصنوعی تنظیم نشده است. مدیر سامانه باید آن را در پنل مدیریت وارد کند.",
        )
    return config, access, api_key


def _adapter(config: AiSettings, access: AiUserAccess, api_key: str) -> OpenAiCompatibleAdapter:
    return OpenAiCompatibleAdapter(
        base_url=config.base_url,
        api_key=api_key,
        model=access.model or config.model,
        timeout_seconds=config.timeout_seconds,
        temperature=config.temperature / 100,
        max_tokens=config.max_tokens,
    )


# ── کاربر ─────────────────────────────────────────────────────────────────


@router.get("/status", response_model=AiStatus)
def ai_status(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> AiStatus:
    """«در دسترس هست یا نه» یک *حالت* است، نه یک استثنا.

    رابط پیش از ساختنِ دکمه همین را می‌پرسد؛ دکمه‌ای که تنها پاسخش «در دسترس
    نیست» باشد، از نبودنِ دکمه بدتر است.
    """
    config = _settings_row(db)
    if not config.enabled:
        return AiStatus(available=False, reason="دستیار در این سامانه فعال نیست", allow_write_actions=False)
    access = _access_row(db, user.id)
    if access is None or not access.enabled:
        return AiStatus(
            available=False,
            reason="دستیار برای حساب شما فعال نشده است",
            allow_write_actions=False,
        )
    if not (decrypt(access.api_key_encrypted) or decrypt(config.api_key_encrypted)):
        return AiStatus(
            available=False, reason="کلید سرویس تنظیم نشده است", allow_write_actions=False
        )
    return AiStatus(
        available=True,
        reason="",
        allow_write_actions=config.allow_write_actions and access.allow_write_actions,
    )


@router.get("/conversations", response_model=list[AiConversationRead])
def list_conversations(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[AiConversationRead]:
    rows = db.scalars(
        select(AiConversation)
        .where(AiConversation.user_id == user.id)
        .order_by(AiConversation.updated_at.desc())
        .limit(30)
    )
    return [AiConversationRead(id=c.id, title=c.title, updated_at=c.updated_at) for c in rows]


@router.get("/conversations/{conversation_id}", response_model=list[AiMessageRead])
def read_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[AiMessageRead]:
    convo = _own_conversation(db, conversation_id, user)
    rows = db.scalars(
        select(AiMessage).where(AiMessage.conversation_id == convo.id).order_by(AiMessage.id)
    )
    return [
        AiMessageRead(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
            actions=_actions_of(m),
        )
        for m in rows
    ]


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    db.delete(_own_conversation(db, conversation_id, user))
    db.commit()
    return None


def _own_conversation(db: Session, conversation_id: int, user: CurrentUser) -> AiConversation:
    convo = db.get(AiConversation, conversation_id)
    if convo is None or convo.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "گفت‌وگو پیدا نشد")
    return convo


def _actions_of(message: AiMessage) -> list[AiActionRead]:
    if not message.actions_json:
        return []
    try:
        return [AiActionRead(**a) for a in json.loads(message.actions_json)]
    except (ValueError, TypeError):
        # ردیفِ خرابِ تاریخچه نباید کل گفت‌وگو را از کار بیندازد.
        return []


@router.post("/chat", response_model=AiChatResponse)
async def chat(
    payload: AiChatRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> AiChatResponse:
    config, access, api_key = _resolve(db, user)

    text = (payload.message or "").strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "پیام خالی است")
    if len(text) > config.max_user_chars:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"پیام از {config.max_user_chars} نویسه بلندتر است",
        )

    if access.daily_message_limit:
        today = datetime.now(UTC) - timedelta(days=1)
        used = db.scalar(
            select(func.count())
            .select_from(AiMessage)
            .join(AiConversation, AiConversation.id == AiMessage.conversation_id)
            .where(
                AiConversation.user_id == user.id,
                AiMessage.role == "user",
                AiMessage.created_at >= today,
            )
        )
        if (used or 0) >= access.daily_message_limit:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"سقف روزانهٔ شما ({access.daily_message_limit} پیام) پر شده است.",
            )

    convo = (
        _own_conversation(db, payload.conversation_id, user)
        if payload.conversation_id
        else AiConversation(user_id=user.id, title=text[:60])
    )
    if convo.id is None:
        db.add(convo)
        db.flush()

    caps = capabilities_of(db, user.id)
    allow_writes = config.allow_write_actions and access.allow_write_actions
    system = build_system_prompt(
        instructions=config.instructions or DEFAULT_INSTRUCTIONS,
        context=context_service.build(db, user, caps, config.context_record_limit),
        user=user,
        caps=caps,
        allow_writes=allow_writes,
        restrict_to_platform=config.restrict_to_platform,
    )

    history = list(
        db.scalars(
            select(AiMessage)
            .where(AiMessage.conversation_id == convo.id)
            .order_by(AiMessage.id.desc())
            .limit(_HISTORY_TURNS)
        )
    )[::-1]
    messages = [ChatMessage("system", system)]
    messages += [ChatMessage(m.role, m.content) for m in history]
    messages.append(ChatMessage("user", text))

    db.add(AiMessage(conversation_id=convo.id, role="user", content=text))
    db.commit()

    try:
        response = await _adapter(config, access, api_key).send(messages)
    except AiUnavailable as err:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(err)) from None
    except AiRequestFailed as err:
        # متنِ خودِ سرویس، بی‌کم‌وکاست: تفاوت ۴۰۱ با «مدل پیدا نشد» چهار رفعِ
        # متفاوت است و کاربر روی سه تای آن می‌تواند کاری بکند.
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, err.detail) from None

    parsed = action_service.parse(response.content) if allow_writes else []
    # کنشِ خواندنی (`find`) بدون تأیید اجرا می‌شود، چون چیزی عوض نمی‌کند.
    proposals = [a for a in parsed if not a.read_only]
    # نثر بدون بلوک: کاربر جمله و دکمه می‌بیند، نه JSON.
    reply = action_service.strip_action_blocks(response.content) if parsed else response.content
    for act in (a for a in parsed if a.read_only):
        result = action_service.execute(db, act, user, caps)
        reply = f"{reply}\n\n**نتیجهٔ {act.summary}:**\n{result}"

    action_dicts = [{"name": a.name, "summary": a.summary, "payload": a.payload} for a in proposals]
    db.add(
        AiMessage(
            conversation_id=convo.id,
            role="assistant",
            content=reply,
            actions_json=json.dumps(action_dicts, ensure_ascii=False) if action_dicts else "",
        )
    )
    convo.updated_at = datetime.now(UTC)
    db.commit()

    return AiChatResponse(
        conversation_id=convo.id,
        reply=reply,
        actions=[AiActionRead(**a) for a in action_dicts],
    )


@router.post("/run-action", response_model=AiRunActionResponse)
def run_action(
    payload: AiRunActionRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> AiRunActionResponse:
    """اجرای یک کنشِ *تأییدشده*.

    نکتهٔ اصلیِ کل این قابلیت همین‌جاست: تنها راهِ تغییرِ داده از مسیر دستیار،
    فراخوانیِ صریحِ همین نقطه است — یعنی فشردنِ دکمه توسط یک آدم.
    """
    config, access, _ = _resolve(db, user)
    if not (config.allow_write_actions and access.allow_write_actions):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دستیار شما اجازهٔ تغییر داده را ندارد")
    _own_conversation(db, payload.conversation_id, user)

    # از نو اعتبارسنجی می‌شود و به آنچه پیش‌تر ذخیره شده اعتماد نمی‌کنیم: بدنهٔ
    # این درخواست از مرورگر می‌آید و مرورگر قابل دست‌کاری است.
    parsed = action_service.parse(
        json.dumps({"action": payload.name, **payload.payload}, ensure_ascii=False)
    )
    if not parsed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این کنش معتبر نیست")

    caps = capabilities_of(db, user.id)
    result = action_service.execute(db, parsed[0], user, caps)
    return AiRunActionResponse(result=result)


# ── مدیریت ────────────────────────────────────────────────────────────────


def _to_settings_read(row: AiSettings) -> AiSettingsRead:
    return AiSettingsRead(
        enabled=row.enabled,
        base_url=row.base_url,
        model=row.model,
        api_key_hint=masked(row.api_key_encrypted),
        api_key_configured=bool(decrypt(row.api_key_encrypted)),
        temperature=row.temperature,
        max_tokens=row.max_tokens,
        timeout_seconds=row.timeout_seconds,
        instructions=row.instructions,
        restrict_to_platform=row.restrict_to_platform,
        context_record_limit=row.context_record_limit,
        allow_write_actions=row.allow_write_actions,
        max_user_chars=row.max_user_chars,
    )


@router.get("/settings", response_model=AiSettingsRead)
def read_settings(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(_admin),
) -> AiSettingsRead:
    return _to_settings_read(_settings_row(db))


@router.put("/settings", response_model=AiSettingsRead)
def update_settings(
    payload: AiSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(_admin),
) -> AiSettingsRead:
    row = _settings_row(db)
    data = payload.model_dump(exclude_unset=True)
    api_key = data.pop("api_key", None)
    for key, value in data.items():
        setattr(row, key, value)
    if api_key is not None:
        row.api_key_encrypted = encrypt(api_key.strip())

    # کلید در لاگ نمی‌آید — فقط اینکه *عوض شد*.
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="ai_settings_changed",
        new_value={"keys": sorted(data), "api_key_changed": api_key is not None},
    )
    db.commit()
    db.refresh(row)
    return _to_settings_read(row)


@router.post("/settings/test", response_model=AiTestResult)
async def test_connection(
    payload: AiTestRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(_admin),
) -> AiTestResult:
    """یک درخواستِ واقعی، و جملهٔ خودِ سرویس در پاسخ.

    نیمی از مشکلات راه‌اندازی «نام مدل اشتباه» است و تنها کسی که این را
    می‌داند خودِ سرویس است. پس «اتصال ناموفق» نه — متنِ او.
    """
    row = _settings_row(db)
    adapter = OpenAiCompatibleAdapter(
        base_url=payload.base_url or row.base_url,
        api_key=(payload.api_key or "").strip() or decrypt(row.api_key_encrypted),
        model=payload.model or row.model,
        timeout_seconds=min(row.timeout_seconds, 30),
        max_tokens=32,
    )
    if not adapter.available:
        return AiTestResult(ok=False, detail="آدرس سرویس، نام مدل و کلید — هر سه باید پر باشند.")
    try:
        response = await adapter.send([ChatMessage("user", "سلام")])
    except (AiUnavailable, AiRequestFailed) as err:
        return AiTestResult(ok=False, detail=getattr(err, "detail", str(err)))
    return AiTestResult(ok=True, detail=f"اتصال برقرار است. پاسخ سرویس: {response.content[:120]}")


@router.get("/access", response_model=list[AiUserAccessRead])
def list_access(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(_admin),
) -> list[AiUserAccessRead]:
    """هر حسابِ فعال، با وضعیت دستیارش — نه فقط آن‌هایی که روشن‌اند.

    فهرستی که فقط روشن‌ها را نشان بدهد، برای «به فلانی هم بده» بی‌فایده است.
    """
    rows = {a.user_id: a for a in db.scalars(select(AiUserAccess))}
    out = []
    for account in db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.id)):
        access = rows.get(account.id)
        out.append(
            AiUserAccessRead(
                user_id=account.id,
                username=account.username,
                display_name=account.full_name or account.username,
                role=account.role.value,
                enabled=bool(access and access.enabled),
                api_key_hint=masked(access.api_key_encrypted) if access else "",
                api_key_configured=bool(access and decrypt(access.api_key_encrypted)),
                model=access.model if access else "",
                allow_write_actions=bool(access.allow_write_actions) if access else True,
                daily_message_limit=access.daily_message_limit if access else 0,
            )
        )
    return out


@router.put("/access/{user_id}", response_model=AiUserAccessRead)
def update_access(
    user_id: int,
    payload: AiUserAccessUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(_admin),
) -> AiUserAccessRead:
    account = db.get(User, user_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب پیدا نشد")

    access = _access_row(db, user_id)
    if access is None:
        access = AiUserAccess(user_id=user_id, enabled=False)
        db.add(access)
        db.flush()

    data = payload.model_dump(exclude_unset=True)
    api_key = data.pop("api_key", None)
    for key, value in data.items():
        setattr(access, key, value)
    if api_key is not None:
        access.api_key_encrypted = encrypt(api_key.strip())

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="ai_access_changed",
        new_value={
            "user_id": user_id,
            **{k: v for k, v in data.items()},
            "api_key_changed": api_key is not None,
        },
    )
    db.commit()
    db.refresh(access)
    return AiUserAccessRead(
        user_id=account.id,
        username=account.username,
        display_name=account.full_name or account.username,
        role=account.role.value,
        enabled=access.enabled,
        api_key_hint=masked(access.api_key_encrypted),
        api_key_configured=bool(decrypt(access.api_key_encrypted)),
        model=access.model,
        allow_write_actions=access.allow_write_actions,
        daily_message_limit=access.daily_message_limit,
    )
