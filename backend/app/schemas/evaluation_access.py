from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EvaluationAccessUpsert(BaseModel):
    unit_supervisor_user_id: int | None = None
    deputy_user_id: int
    ceo_user_id: int


class EvaluationAccessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    personnel_id: int
    unit_supervisor_user_id: int | None
    deputy_user_id: int
    ceo_user_id: int
    updated_by_user_id: int | None
    updated_at: datetime
