from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EvaluationAccessUpsert(BaseModel):
    # هر دو مرحلهٔ میانی می‌توانند غایب باشند. مسئول واحدِ خالی یعنی مسیر «مدیر»؛
    # معاونتِ خالی یعنی فرد مستقیم زیر نظر مدیرعامل است و مرحلهٔ معاونت پریده
    # می‌شود. تنها مدیرعامل اجباری است — کسی باید پرونده را ببندد.
    unit_supervisor_user_id: int | None = None
    deputy_user_id: int | None = None
    ceo_user_id: int


class EvaluationAccessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    personnel_id: int
    unit_supervisor_user_id: int | None
    deputy_user_id: int | None
    ceo_user_id: int
    updated_by_user_id: int | None
    updated_at: datetime
