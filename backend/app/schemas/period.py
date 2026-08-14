from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import PeriodStatus


class PeriodCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    starts_on: date
    ends_on: date

    @model_validator(mode="after")
    def _dates_in_order(self) -> "PeriodCreate":
        if self.ends_on <= self.starts_on:
            raise ValueError("تاریخ پایان دوره باید بعد از تاریخ شروع باشد")
        return self


class PeriodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    starts_on: date
    ends_on: date
    status: PeriodStatus
    created_at: datetime
    closed_at: datetime | None


class NotStartedPersonnel(BaseModel):
    personnel_id: int
    full_name: str
    org_unit: str


class PeriodProgress(BaseModel):
    """پیشرفت دوره: چند نفر واجد ارزیابی‌اند، برای چند نفر شروع/نهایی شده و چه کسانی جا مانده‌اند."""

    period: PeriodRead
    eligible: int
    started: int
    finalized: int
    # پرونده‌هایی که شروع شده‌اند ولی هنوز نهایی نشده‌اند. این عدد نقطهٔ تصمیمِ
    # بستن دوره است: بستن دوره‌ای که ده پرونده وسط گردش‌کار دارد، اشتباهی است که
    # باید *پیش* از انجامش دیده شود، نه بعدش.
    in_progress: int
    # تعداد کلِ شروع‌نشده‌ها، حتی وقتی فهرست زیر بریده شده است — وگرنه با یک
    # سازمان بزرگ، «۵۰ نفر شروع نکرده‌اند» به‌غلط کل ماجرا به‌نظر می‌رسید.
    not_started_total: int
    not_started: list[NotStartedPersonnel]
