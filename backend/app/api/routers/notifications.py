from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.enums import DeliveryChannel
from app.models.notification import Notification
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.schemas.notification import (
    NotificationPage,
    NotificationPreferences,
    NotificationPreferencesRead,
    NotificationRead,
)
from app.services import channels

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationPage)
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=15, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationPage:
    base = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        base = base.where(Notification.read_at.is_(None))

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    unread = (
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == current_user.id, Notification.read_at.is_(None))
        )
        or 0
    )
    items = list(
        db.scalars(base.order_by(Notification.created_at.desc()).limit(limit).offset(offset))
    )
    return NotificationPage(
        total=total, unread=unread, items=[NotificationRead.model_validate(n) for n in items]
    )


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Notification:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="اعلان یافت نشد")
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(notification)
    return notification


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    db.commit()


@router.get("/preferences", response_model=NotificationPreferencesRead)
def get_preferences(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationPreferencesRead:
    """ارجحیت تماس کاربر، به‌علاوهٔ اینکه سازمان کدام کانال را اصلاً تنظیم کرده."""
    user = db.get(User, current_user.id)
    configured = {channel.kind for channel in channels.available()}
    return NotificationPreferencesRead(
        email=user.email,
        phone=user.phone,
        notify_by_email=user.notify_by_email,
        notify_by_sms=user.notify_by_sms,
        email_available=DeliveryChannel.email in configured,
        sms_available=DeliveryChannel.sms in configured,
    )


@router.put("/preferences", response_model=NotificationPreferencesRead)
def update_preferences(
    payload: NotificationPreferences,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationPreferencesRead:
    """هر کاربر فقط ارجحیت خودش را تعیین می‌کند.

    روشن‌کردن کانالی که نشانی‌اش خالی است رد می‌شود: تیکی که هیچ اثری ندارد،
    کاربر را منتظر پیامی می‌گذارد که هرگز نمی‌آید.
    """
    user = db.get(User, current_user.id)
    email = payload.email or None
    phone = payload.phone or None

    if payload.notify_by_email and not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای دریافت ایمیل، ابتدا نشانی ایمیل خود را وارد کنید",
        )
    if payload.notify_by_sms and not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای دریافت پیامک، ابتدا شمارهٔ همراه خود را وارد کنید",
        )

    user.email = email
    user.phone = phone
    user.notify_by_email = payload.notify_by_email
    user.notify_by_sms = payload.notify_by_sms
    db.commit()
    return get_preferences(db=db, current_user=current_user)
