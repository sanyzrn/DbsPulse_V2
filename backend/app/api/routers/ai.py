"""همکار هوشمند — گفت‌وگو، ابزارها، فایل‌ها، تأیید، و تنظیماتش.

دو دستهٔ کاملاً جدا در یک فایل:

* مسیرهای *کاربرِ* همکار: `/chat`, `/status`, `/conversations`, `/tools`,
  `/pending/{id}/confirm|reject`, `/conversations/{id}/attachments`.
  معاونتی که فقط باید بپرسد همین‌ها را می‌بیند و بس.
* `/api/ai/settings`, `/access` — پشتِ `manage_ai`. کلید API، متنِ راهنما،
  اینکه چه کسی دستیار دارد.

جداکردنشان در سطح مجوز است و نه در سطح رابط: پنهان‌کردنِ یک دکمه در فرانت‌اند
تنظیمات را محافظت نمی‌کند.
"""
import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_capability
from app.core.ai_providers import PROVIDERS, PROVIDERS_BY_ID
from app.core.crypto import decrypt, encrypt, masked
from app.db.session import get_db
from app.models.ai import (
    DEFAULT_INSTRUCTIONS,
    AiConversation,
    AiMessage,
    AiPendingAction,
    AiSettings,
    AiUpload,
    AiUserAccess,
)
from app.models.enums import Capability
from app.models.user import User
from app.schemas.ai import (
    AiChatRequest,
    AiChatResponse,
    AiConversationRead,
    AiConversationRenameRequest,
    AiMessageRead,
    AiPendingActionRead,
    AiPendingDecisionRequest,
    AiProviderOption,
    AiSettingsRead,
    AiSettingsUpdate,
    AiStatus,
    AiStepRead,
    AiTestRequest,
    AiTestResult,
    AiToolRead,
    AiUploadRead,
    AiUserAccessRead,
    AiUserAccessUpdate,
)
from app.schemas.auth import CurrentUser
from app.services.ai import confirmations
from app.services.ai.orchestrator import run_turn
from app.services.ai.port import AiRequestFailed, AiUnavailable
from app.services.ai.provider import OpenAiCompatibleAdapter
from app.services.ai.tools import base as tools_base
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


def _allow_writes(config: AiSettings, access: AiUserAccess) -> bool:
    return bool(config.allow_write_actions and access.allow_write_actions)


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
        allow_write_actions=_allow_writes(config, access),
        allow_uploads=bool(config.allow_uploads),
    )


@router.get("/tools", response_model=list[AiToolRead])
def list_tools(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[AiToolRead]:
    """ابزارهایی که *این* کاربر واقعاً دارد — رابط از روی همین پیشنهاد می‌سازد.

    تبلیغِ ابزاری که اجرا نمی‌شود، دکمهٔ مرده است؛ پس فهرست از همان گاردِ
    اجرا می‌آید.
    """
    _resolve(db, user)
    caps = set(capabilities_of(db, user.id))
    config = _settings_row(db)
    access = _access_row(db, user.id)
    allow_writes = _allow_writes(config, access) if access else False
    specs = tools_base.allowed_tools(user, caps, allow_writes=allow_writes)
    return [
        AiToolRead(
            name=s.name,
            description=s.description,
            category=s.category,
            read_only=s.read_only,
            risky=s.risky,
        )
        for s in sorted(specs, key=lambda t: (t.category, t.name))
    ]


@router.get("/conversations", response_model=list[AiConversationRead])
def list_conversations(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[AiConversationRead]:
    rows = db.scalars(
        select(AiConversation)
        .where(AiConversation.user_id == user.id)
        .order_by(AiConversation.updated_at.desc())
        .limit(50)
    )
    return [AiConversationRead(id=c.id, title=c.title, updated_at=c.updated_at) for c in rows]


@router.post("/conversations", response_model=AiConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> AiConversationRead:
    """گفت‌وگوی خالی، از قبل — دکمهٔ «گفت‌وگوی تازه» بدون پیام هم معنا دارد."""
    _resolve(db, user)
    convo = AiConversation(user_id=user.id, title="")
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return AiConversationRead(id=convo.id, title=convo.title, updated_at=convo.updated_at)


@router.patch("/conversations/{conversation_id}", response_model=AiConversationRead)
def rename_conversation(
    conversation_id: int,
    payload: AiConversationRenameRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> AiConversationRead:
    convo = _own_conversation(db, conversation_id, user)
    convo.title = payload.title.strip()[:200]
    db.commit()
    db.refresh(convo)
    return AiConversationRead(id=convo.id, title=convo.title, updated_at=convo.updated_at)


@router.get("/conversations/{conversation_id}", response_model=list[AiMessageRead])
def read_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[AiMessageRead]:
    convo = _own_conversation(db, conversation_id, user)
    rows = list(db.scalars(
        select(AiMessage).where(AiMessage.conversation_id == convo.id).order_by(AiMessage.id)
    ))
    messages = [_to_message_read(m) for m in rows]
    # کارت‌های تأییدِ معلق، به آخرین پیامِ دستیار می‌چسبند — وضعیت‌شان زنده از
    # جدول می‌آید، نه عکسِ لحظهٔ چت: «قبلاً تأیید شده» همیشه حقیقتِ الان است.
    live = _pending_of_conversation(db, convo.id)
    if live:
        for message in reversed(messages):
            if message.role == "assistant":
                message.pending = live
                break
    return messages


@router.get("/conversations/{conversation_id}/attachments", response_model=list[AiUploadRead])
def list_attachments(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[AiUploadRead]:
    convo = _own_conversation(db, conversation_id, user)
    rows = db.scalars(
        select(AiUpload).where(AiUpload.conversation_id == convo.id).order_by(AiUpload.id)
    )
    return [_to_upload_read(row) for row in rows]


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    convo = _own_conversation(db, conversation_id, user)
    db.delete(convo)
    db.commit()
    return None


def _own_conversation(db: Session, conversation_id: int, user: CurrentUser) -> AiConversation:
    convo = db.get(AiConversation, conversation_id)
    if convo is None or convo.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "گفت‌وگو پیدا نشد")
    return convo


def _to_upload_read(upload: AiUpload) -> AiUploadRead:
    try:
        structure = json.loads(upload.structure_json or "{}")
    except ValueError:
        structure = {}
    kind = structure.get("kind", "file")
    return AiUploadRead(
        id=upload.id,
        filename=upload.filename,
        kind=kind,
        size_bytes=upload.size_bytes,
        total_rows=int(structure.get("total_rows", 0)),
        valid_count=int(structure.get("valid_count", 0)),
        invalid_count=int(structure.get("invalid_count", 0)),
        committed=bool(structure.get("committed")),
        note=str(structure.get("note", "")),
    )


def _to_message_read(message: AiMessage) -> AiMessageRead:
    steps: list[AiStepRead] = []
    if message.meta_json:
        try:
            meta = json.loads(message.meta_json)
        except ValueError:
            meta = {}
        steps = [AiStepRead(**s) for s in meta.get("steps", []) if isinstance(s, dict)]
    return AiMessageRead(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
        actions=[],
        steps=steps,
        pending=[],
    )


def _pending_of_conversation(db: Session, conversation_id: int) -> list[AiPendingActionRead]:
    rows = db.scalars(
        select(AiPendingAction)
        .where(AiPendingAction.conversation_id == conversation_id)
        .order_by(AiPendingAction.id.desc())
        .limit(20)
    )
    return [
        AiPendingActionRead(
            id=row.id,
            tool=row.tool_name,
            summary=row.summary,
            arguments=json.loads(row.arguments_json or "{}"),
            status=row.status,
            result_text=row.result_text,
            expires_at=row.expires_at,
        )
        for row in rows
    ]


@router.post(
    "/conversations/{conversation_id}/attachments",
    response_model=AiUploadRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    conversation_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> AiUploadRead:
    """بارگذاری فایل در گفت‌وگو — مرحله‌بندی، نه ورود.

    هیچ ردیفی ساخته نمی‌شود؛ فقط فایل ذخیره و با اعتبارسنجیِ رسمی خوانده
    می‌شود تا دستیار بتواند خطاها را توضیح بدهد و مسیرِ درست‌کردن را بپرسد.
    """
    config, access, _ = _resolve(db, user)
    if not config.allow_uploads:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "بارگذاری فایل در دستیار فعال نیست")
    convo = _own_conversation(db, conversation_id, user)

    content = await file.read()
    max_bytes = max(1, int(config.max_upload_mb)) * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"حجم فایل بیش از حد مجاز است (حداکثر {config.max_upload_mb} مگابایت)",
        )
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فایل خالی است")

    from app.services.ai.tools.uploads import stage_upload

    upload, _summary = stage_upload(
        db,
        user,
        convo.id,
        filename=file.filename or "file",
        mime_type=file.content_type or "",
        content=content,
    )
    log_event(
        db,
        actor_user_id=user.id,
        event_type="ai_upload_staged",
        new_value={
            "upload_id": upload.id,
            "filename": upload.filename,
            "size": len(content),
            "conversation_id": convo.id,
            "via": "ai_copilot",
        },
    )
    db.commit()
    return _to_upload_read(upload)


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

    allow_writes = _allow_writes(config, access)
    user_message = AiMessage(conversation_id=convo.id, role="user", content=text)
    db.add(user_message)
    db.flush()

    try:
        result = await run_turn(
            db,
            user=user,
            conversation=convo,
            config=config,
            api_key=api_key,
            access_model=access.model or config.model,
            adapter_factory=lambda: _adapter(config, access, api_key),
            user_text=text,
            allow_writes=allow_writes,
            user_message_id=user_message.id,
        )
    except (AiUnavailable, AiRequestFailed) as err:
        db.commit()
        detail = getattr(err, "detail", str(err))
        # متنِ خودِ سرویس، بی‌کم‌وکاست: تفاوت ۴۰۱ با «مدل پیدا نشد» چهار رفعِ
        # متفاوت است و کاربر روی سه تای آن می‌تواند کاری بکند.
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY if isinstance(err, AiRequestFailed) else status.HTTP_503_SERVICE_UNAVAILABLE,
            detail,
        ) from None

    db.add(
        AiMessage(
            conversation_id=convo.id,
            role="assistant",
            content=result.reply,
            meta_json=result.meta_json(),
        )
    )
    convo.updated_at = datetime.now(UTC)
    db.commit()

    return AiChatResponse(
        conversation_id=convo.id,
        reply=result.reply,
        steps=[AiStepRead(**s.to_dict()) for s in result.steps],
        pending=[AiPendingActionRead(**p) for p in result.pending],
        usage=result.usage,
    )


# ── تأیید / رد ────────────────────────────────────────────────────────────


@router.post("/pending/{pending_id}/confirm", response_model=AiChatResponse)
def confirm_pending(
    pending_id: int,
    _payload: AiPendingDecisionRequest | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> AiChatResponse:
    """تأییدِ یک کنشِ در انتظار — تنها نقطهٔ اجرای تغییراتِ پیشنهادیِ دستیار.

    همه‌چیز از نو اعتبارسنجی می‌شود: مالکیت، انقضا، مجوزِ امروز، آرگومان‌ها.
    """
    config, access, _ = _resolve(db, user)
    row, summary = confirmations.confirm(db, user=user, pending_id=pending_id, config=config, access=access)
    return AiChatResponse(
        conversation_id=row.conversation_id,
        reply=summary,
        steps=[
            AiStepRead(
                tool=row.tool_name,
                status="confirmed",
                summary=summary,
                detail={"result": row.result_text},
            )
        ],
        pending=[],
    )


@router.post("/pending/{pending_id}/reject", response_model=AiPendingActionRead)
def reject_pending(
    pending_id: int,
    _payload: AiPendingDecisionRequest | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> AiPendingActionRead:
    _resolve(db, user)
    row = confirmations.reject(db, user=user, pending_id=pending_id)
    return AiPendingActionRead(
        id=row.id,
        tool=row.tool_name,
        summary=row.summary,
        arguments=json.loads(row.arguments_json or "{}"),
        status=row.status,
        result_text=row.result_text,
        expires_at=row.expires_at,
    )


@router.get("/pending", response_model=list[AiPendingActionRead])
def list_pending(
    conversation_id: int | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[AiPendingActionRead]:
    """کنش‌های در انتظارِ تصمیمِ من — رابط با این، کارت‌های معلق را بازسازی می‌کند."""
    stmt = (
        select(AiPendingAction)
        .where(AiPendingAction.user_id == user.id, AiPendingAction.status == "pending")
        .order_by(AiPendingAction.id.desc())
        .limit(20)
    )
    if conversation_id:
        stmt = stmt.where(AiPendingAction.conversation_id == int(conversation_id))
    rows = list(db.scalars(stmt))
    return [
        AiPendingActionRead(
            id=row.id,
            tool=row.tool_name,
            summary=row.summary,
            arguments=json.loads(row.arguments_json or "{}"),
            status=row.status,
            result_text=row.result_text,
            expires_at=row.expires_at,
        )
        for row in rows
    ]


# ── مدیریت ────────────────────────────────────────────────────────────────


def _to_settings_read(row: AiSettings) -> AiSettingsRead:
    return AiSettingsRead(
        enabled=row.enabled,
        provider=row.provider,
        providers=[
            AiProviderOption(
                id=p.id, label=p.label, base_url=p.base_url,
                default_model=p.default_model, note=p.note,
            )
            for p in PROVIDERS
        ],
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
        max_tool_iterations=row.max_tool_iterations,
        allow_uploads=row.allow_uploads,
        max_upload_mb=row.max_upload_mb,
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

    # سرویسِ ناشناخته رد می‌شود و به «سفارشی» نمی‌افتد: افتادنِ خاموش یعنی
    # فرم چیزی را ذخیره کند که کاربر انتخاب نکرده.
    if data.get("provider") is not None and data["provider"] not in PROVIDERS_BY_ID:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سرویس انتخاب‌شده شناخته نشد")

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
        response = await adapter.send([ChatMessageCompat("سلام")])
    except (AiUnavailable, AiRequestFailed) as err:
        return AiTestResult(ok=False, detail=getattr(err, "detail", str(err)))
    return AiTestResult(ok=True, detail=f"اتصال برقرار است. پاسخ سرویس: {response.content[:120]}")


def ChatMessageCompat(content: str):
    from app.services.ai.port import ChatMessage

    return ChatMessage("user", content)


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
