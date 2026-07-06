from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.enums import UserRole
from app.models.evaluation import EvaluationRecord
from app.models.user import User
from app.schemas.audit_log import AuditLogPage, AuditLogRead
from app.schemas.auth import CurrentUser

router = APIRouter(prefix="/api/audit-log", tags=["audit-log"])


@router.get("", response_model=AuditLogPage)
def list_audit_log(
    event_type: str | None = None,
    evaluation_record_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> AuditLogPage:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    filters = []
    if event_type is not None:
        filters.append(AuditLog.event_type == event_type)
    if evaluation_record_id is not None:
        filters.append(AuditLog.evaluation_record_id == evaluation_record_id)

    total = db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0

    # نام کاربر و کد ارزیابی با JOIN در همان کوئری صفحه حل می‌شوند؛ نسخه قبلی کل
    # جدول users و evaluation_records را برای ۵۰ ردیف در حافظه بارگذاری می‌کرد.
    rows = db.execute(
        select(AuditLog, User.username, EvaluationRecord.evaluation_code)
        .join(User, User.id == AuditLog.actor_user_id, isouter=True)
        .join(EvaluationRecord, EvaluationRecord.id == AuditLog.evaluation_record_id, isouter=True)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    items = [
        AuditLogRead(
            id=row.id,
            evaluation_record_id=row.evaluation_record_id,
            evaluation_code=evaluation_code,
            actor_user_id=row.actor_user_id,
            actor_username=username,
            event_type=row.event_type,
            old_value=row.old_value,
            new_value=row.new_value,
            created_at=row.created_at,
        )
        for row, username, evaluation_code in rows
    ]

    return AuditLogPage(total=total, items=items)
