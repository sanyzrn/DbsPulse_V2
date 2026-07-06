from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import CommentStage, EvaluationStage, EvaluationStatus

# مرحله نمایشی از وضعیت مشتق می‌شود؛ ستون جداگانه‌ای در دیتابیس ندارد (G1 در PROJECT_AUDIT).
_STAGE_BY_STATUS: dict[EvaluationStatus, EvaluationStage] = {
    EvaluationStatus.draft: EvaluationStage.supervisor_scoring,
    EvaluationStatus.submitted: EvaluationStage.hr_review,
    EvaluationStatus.hr_approved: EvaluationStage.deputy_review,
    EvaluationStatus.deputy_approved: EvaluationStage.ceo_final,
    EvaluationStatus.finalized: EvaluationStage.ceo_final,
}


class EvaluationCreate(BaseModel):
    subject_personnel_id: int


class ScoreInput(BaseModel):
    indicator_id: int
    score: int = Field(ge=1, le=5)
    evidence_text: str | None = None


class ScoresUpsert(BaseModel):
    scores: list[ScoreInput]


class ScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    indicator_id: int
    score: int
    evidence_text: str | None


class CommentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    comment_text: str = Field(min_length=1)


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    commenter_user_id: int
    commenter_username: str | None = None
    stage: CommentStage
    comment_text: str
    created_at: datetime


class ReturnRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reason: str = Field(min_length=1)


class EvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evaluation_code: str
    subject_personnel_id: int
    subject_full_name: str
    period_id: int | None
    unit_supervisor_user_id: int | None
    deputy_user_id: int
    ceo_user_id: int
    status: EvaluationStatus
    general_score_pct: float | None
    specialized_score_pct: float | None
    final_weighted_pct: float | None
    recommendation: str | None
    evaluator_comment: str | None
    created_at: datetime
    finalized_at: datetime | None
    acknowledged_at: datetime | None = None
    # آیا این پرونده قبلاً حداقل یک‌بار برگشت خورده — تا صف بررسی بتواند آن را
    # از یک ثبت/تأیید تازه متمایز کند (روی list_evaluations پر می‌شود، نه اینجا)
    was_returned: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def stage(self) -> EvaluationStage:
        return _STAGE_BY_STATUS[self.status]


class EvaluationDetail(EvaluationRead):
    scores: list[ScoreRead] = []
    comments: list[CommentRead] = []


class EvaluationPage(BaseModel):
    total: int
    items: list[EvaluationRead]


class EvaluatorCommentUpdate(BaseModel):
    evaluator_comment: str


class MyEvaluationRead(BaseModel):
    """نمای محدود پرونده برای خود کارمند: فقط نتیجه نهایی، بدون شواهد و کامنت‌های داخلی."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    evaluation_code: str
    subject_full_name: str
    period_id: int | None
    general_score_pct: float | None
    specialized_score_pct: float | None
    final_weighted_pct: float | None
    recommendation: str | None
    finalized_at: datetime | None
    acknowledged_at: datetime | None


class MyEvaluationPage(BaseModel):
    total: int
    items: list[MyEvaluationRead]
