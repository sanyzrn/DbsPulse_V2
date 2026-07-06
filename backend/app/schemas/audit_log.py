from datetime import datetime

from pydantic import BaseModel


class AuditLogRead(BaseModel):
    id: int
    evaluation_record_id: int | None
    evaluation_code: str | None
    actor_user_id: int
    actor_username: str | None
    event_type: str
    old_value: dict | None
    new_value: dict | None
    created_at: datetime


class AuditLogPage(BaseModel):
    total: int
    items: list[AuditLogRead]
