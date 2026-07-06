from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    message: str
    link: str | None
    evaluation_record_id: int | None
    created_at: datetime
    read_at: datetime | None


class NotificationPage(BaseModel):
    total: int
    unread: int
    items: list[NotificationRead]


class ExpiringContract(BaseModel):
    personnel_id: int
    full_name: str
    org_unit: str
    contract_end_date: date
    days_remaining: int
    has_open_evaluation: bool
