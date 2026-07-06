from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import PersonnelStatus


class PersonnelBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    personnel_code: str = Field(min_length=1, max_length=50)
    full_name: str = Field(min_length=1, max_length=200)
    job_title: str = Field(min_length=1, max_length=150)
    is_manager: bool = False
    org_unit: str = Field(min_length=1, max_length=150)
    contract_start_date: date
    contract_end_date: date


class PersonnelCreate(PersonnelBase):
    @model_validator(mode="after")
    def _contract_dates_in_order(self) -> "PersonnelCreate":
        if self.contract_end_date <= self.contract_start_date:
            raise ValueError("تاریخ پایان قرارداد باید بعد از تاریخ شروع قرارداد باشد")
        return self


class PersonnelUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    personnel_code: str | None = Field(default=None, min_length=1, max_length=50)
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    job_title: str | None = Field(default=None, min_length=1, max_length=150)
    is_manager: bool | None = None
    org_unit: str | None = Field(default=None, min_length=1, max_length=150)
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    status: PersonnelStatus | None = None


class PersonnelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    personnel_code: str
    full_name: str
    job_title: str
    is_manager: bool
    org_unit: str
    contract_start_date: date
    contract_end_date: date
    status: PersonnelStatus
    created_at: datetime
    updated_at: datetime


class PersonnelPage(BaseModel):
    total: int
    items: list[PersonnelRead]
