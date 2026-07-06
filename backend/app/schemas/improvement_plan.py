from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ImprovementPlanStatus


class GoalCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    description: str = Field(min_length=1)


class GoalUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    description: str | None = Field(default=None, min_length=1)
    is_done: bool | None = None


class GoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str
    is_done: bool
    display_order: int


class ImprovementPlanCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    evaluation_record_id: int
    title: str = Field(min_length=1, max_length=200)
    review_date: date
    owner_user_id: int | None = None
    summary: str | None = None
    # اهداف اولیه می‌توانند همراه ساخت برنامه ارسال شوند (اختیاری)
    goals: list[str] = []


class ImprovementPlanUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    review_date: date | None = None
    owner_user_id: int | None = None
    summary: str | None = None
    follow_up_evaluation_id: int | None = None


class ImprovementPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evaluation_record_id: int
    personnel_id: int
    personnel_full_name: str
    title: str
    owner_user_id: int | None
    status: ImprovementPlanStatus
    review_date: date
    summary: str | None
    follow_up_evaluation_id: int | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class ImprovementPlanDetail(ImprovementPlanRead):
    goals: list[GoalRead] = []


class ImprovementPlanPage(BaseModel):
    total: int
    items: list[ImprovementPlanRead]


class EligibleEvaluation(BaseModel):
    """ارزیابی نهایی‌شده با نتیجه «تمدید مشروط» که هنوز برنامه بهبود ندارد."""

    evaluation_record_id: int
    evaluation_code: str
    personnel_id: int
    personnel_full_name: str
    final_weighted_pct: float | None
    finalized_at: datetime | None
