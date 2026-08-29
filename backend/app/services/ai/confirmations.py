"""نقطهٔ تأیید: جایی که پیشنهادِ مدل، کارِ آدم می‌شود.

کل معماری در یک جمله: **تنها راهِ تغییرِ داده از مسیر دستیار، عبور از همین
فایل است** — و این‌جا برای بار دوم همه‌چیز سنجیده می‌شود:

* مالکیتِ پیشنهاد (تأییدکننده همان کسی است که گفت‌وگو برایش بود)؛
* زنده‌بودنِ پیشنهاد (اجرا‌نشده و منقضی‌نشده)؛
* مجوزِ *امروزِ* کاربر (ممکن است از دیروز سلب شده باشد)؛
* سالم‌بودنِ آرگومان‌ها (دوباره از JSON خوانده می‌شود، نه اعتماد به مرورگر).

نتیجهٔ اجرا در خودِ ردیف می‌نشیند تا «چه شد» همیشه قابل‌خواندن بماند، و یک
پیامِ دستیارِ تازه با همان نتیجه به گفت‌وگو اضافه می‌شود تا تاریخچه روان
بماند.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.ai import AiConversation, AiMessage, AiPendingAction
from app.schemas.auth import CurrentUser
from app.services.ai.tools import base as tools_base
from app.services.ai.tools.base import ToolContext
from app.services.audit import log_event
from app.services.authorization import capabilities_of


def _pending_or_404(db: Session, pending_id: int, user: CurrentUser) -> AiPendingAction:
    row = db.get(AiPendingAction, int(pending_id))
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "این پیشنهاد پیدا نشد")
    return row


def _ensure_decidable(db: Session, row: AiPendingAction, user: CurrentUser, config, access) -> None:
    """چهار گاردِ پیش از اجرا — هر کدام پیامِ مخصوص خودش را دارد."""
    if row.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "این پیشنهاد قبلاً تعیین تکلیف شده است")
    if row.expires_at and row.expires_at < datetime.now(UTC):
        row.status = "expired"
        db.add(row)
        db.commit()
        raise HTTPException(status.HTTP_410_GONE, "این پیشنهاد منقضی شده است؛ از دستیار بخواهید تازه بسازد")

    if not config.enabled or access is None or not access.enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دستیار برای حساب شما دیگر فعال نیست")

    conversation = db.get(AiConversation, row.conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "گفت‌وگوی این پیشنهاد پیدا نشد")


def confirm(
    db: Session,
    *,
    user: CurrentUser,
    pending_id: int,
    config,
    access,
) -> tuple[AiPendingAction, str]:
    """تأیید و اجرا. خروجی: ردیفِ به‌روزشده + جملهٔ نتیجه برای نمایش."""
    row = _pending_or_404(db, pending_id, user)
    _ensure_decidable(db, row, user, config, access)

    caps = set(capabilities_of(db, user.id))
    allow_writes = bool(config.allow_write_actions and access.allow_write_actions)
    spec = tools_base.get_tool(row.tool_name)
    if spec is None:
        row.status = "expired"
        db.add(row)
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این کنش دیگر در سامانه وجود ندارد")
    if not allow_writes or spec.read_only:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "اجازهٔ تغییر داده ندارید")
    tools_base.guard(spec, user, caps)

    arguments = json.loads(row.arguments_json or "{}")
    ctx = ToolContext(db=db, user=user, caps=frozenset(caps), conversation_id=row.conversation_id)

    # کنشِ دوپله‌ای (ورود گروهی): پیشنهادش فقط «اعتبارسنجی» بود؛ اجرای واقعی
    # تابعِ جداگانه‌ای دارد که خودش هنگام ثبتِ ابزار اعلام می‌کند.
    runner = getattr(spec.handler, "executor", None) or spec.handler

    try:
        outcome = runner(ctx, **tools_base._clean_kwargs(runner, arguments))
        row.status = "confirmed"
        row.result_text = outcome.summary or "انجام شد"
    except HTTPException as err:
        row.status = "failed"
        row.result_text = str(err.detail)
        row.decided_at = datetime.now(UTC)
        db.add(row)
        log_event(
            db,
            actor_user_id=user.id,
            event_type="ai_action_failed",
            new_value={"pending_action_id": row.id, "tool": row.tool_name, "error": str(err.detail)[:200], "via": "ai_copilot"},
        )
        db.commit()
        raise
    except Exception as err:  # noqa: BLE001
        row.status = "failed"
        row.result_text = str(err)[:200]
        row.decided_at = datetime.now(UTC)
        db.add(row)
        db.commit()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "اجرای این کنش شکست خورد؛ جزئیات در گزارش رویدادها ثبت شد") from err

    row.decided_at = datetime.now(UTC)
    db.add(row)

    db.add(
        AiMessage(
            conversation_id=row.conversation_id,
            role="assistant",
            content=f"✅ {outcome.summary or 'انجام شد'}",
            meta_json=json.dumps(
                {
                    "steps": [
                        {
                            "tool": row.tool_name,
                            "status": "confirmed",
                            "summary": outcome.summary,
                            "detail": outcome.ui,
                        }
                    ],
                    "pending": [],
                    "confirmed_pending_action_id": row.id,
                },
                ensure_ascii=False,
            ),
        )
    )

    log_event(
        db,
        actor_user_id=user.id,
        event_type="ai_action_confirmed",
        new_value={
            "pending_action_id": row.id,
            "tool": row.tool_name,
            "arguments": tools_base.sanitize_arguments(arguments),
            "conversation_id": row.conversation_id,
            "via": "ai_copilot",
        },
    )
    db.commit()
    return row, outcome.summary


def reject(
    db: Session,
    *,
    user: CurrentUser,
    pending_id: int,
) -> AiPendingAction:
    row = _pending_or_404(db, pending_id, user)
    if row.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "این پیشنهاد قبلاً تعیین تکلیف شده است")
    row.status = "rejected"
    row.decided_at = datetime.now(UTC)
    db.add(row)
    db.add(
        AiMessage(
            conversation_id=row.conversation_id,
            role="assistant",
            content="رد شد. هیچ تغییری اعمال نکردم.",
            meta_json=json.dumps(
                {
                    "steps": [{"tool": row.tool_name, "status": "rejected", "summary": row.summary, "detail": {}}],
                    "pending": [],
                    "rejected_pending_action_id": row.id,
                },
                ensure_ascii=False,
            ),
        )
    )
    log_event(
        db,
        actor_user_id=user.id,
        event_type="ai_action_rejected",
        new_value={"pending_action_id": row.id, "tool": row.tool_name, "via": "ai_copilot"},
    )
    db.commit()
    return row
