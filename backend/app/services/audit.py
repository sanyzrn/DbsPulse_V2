from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_event(
    db: Session,
    actor_user_id: int,
    event_type: str,
    evaluation_record_id: int | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            evaluation_record_id=evaluation_record_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            old_value=old_value,
            new_value=new_value,
        )
    )
