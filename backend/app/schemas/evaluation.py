from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.text_limits import (
    BONUS_REASON_MAX,
    COMMENT_MAX,
    EVALUATOR_COMMENT_MAX,
    EVIDENCE_MAX,
    OBJECTION_MAX,
    REASON_MAX,
    SELF_ASSESSMENT_NOTE_MAX,
    SELF_ASSESSMENT_SUMMARY_MAX,
)
from app.models.enums import CommentStage, EvaluationStage, EvaluationStatus

# مرحله نمایشی از وضعیت مشتق می‌شود؛ ستون جداگانه‌ای در دیتابیس ندارد (G1 در PROJECT_AUDIT).
_STAGE_BY_STATUS: dict[EvaluationStatus, EvaluationStage] = {
    EvaluationStatus.draft: EvaluationStage.supervisor_scoring,
    EvaluationStatus.submitted: EvaluationStage.hr_review,
    EvaluationStatus.hr_approved: EvaluationStage.deputy_review,
    EvaluationStatus.deputy_approved: EvaluationStage.ceo_final,
    EvaluationStatus.finalized: EvaluationStage.ceo_final,
    # cancelled عمداً این‌جا نیست: پروندهٔ لغوشده در هیچ مرحله‌ای «نیست» و نسبت‌دادن
    # یک مرحله به آن گمراه‌کننده است. stage برای این حالت None برمی‌گردد.
}

# برچسب‌های مرحله از دید خودِ کارمند — «چه کسی الان باید اقدام کند»، نه اصطلاح داخلی
# گردش‌کار. کارمند نباید برای فهمیدن وضعیت پرونده‌اش واژگان سازمانی یاد بگیرد.
_EMPLOYEE_STAGE_LABELS: dict[EvaluationStatus, str] = {
    EvaluationStatus.draft: "در حال تکمیل توسط ارزیاب",
    EvaluationStatus.submitted: "در حال بررسی منابع انسانی",
    EvaluationStatus.hr_approved: "در انتظار تأیید معاونت",
    EvaluationStatus.deputy_approved: "در انتظار تأیید مدیرعامل",
}


class EvaluationCreate(BaseModel):
    subject_personnel_id: int


class ScoreInput(BaseModel):
    indicator_id: int
    score: int = Field(ge=1, le=5)
    evidence_text: str | None = Field(default=None, max_length=EVIDENCE_MAX)


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

    comment_text: str = Field(min_length=1, max_length=COMMENT_MAX)
    # اگر مقدار داشته باشد، این یک پاسخ threaded به یک کامنتِ سطح‌بالاست (فقط یک سطح عمق).
    parent_comment_id: int | None = None


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    commenter_user_id: int
    commenter_username: str | None = None
    parent_comment_id: int | None = None
    stage: CommentStage
    comment_text: str
    created_at: datetime


class ReturnRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=REASON_MAX)


class CancelRequest(BaseModel):
    """لغو پرونده دلیل اجباری دارد — این یک تصمیم ثبت‌شدنی است، نه یک پاک‌کردن بی‌صدا."""

    model_config = ConfigDict(str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=REASON_MAX)


class HrHandover(BaseModel):
    """واگذاری مسئولیتِ HR یک پرونده به کاربر دیگری از منابع انسانی."""

    model_config = ConfigDict(str_strip_whitespace=True)

    new_hr_user_id: int
    reason: str = Field(min_length=1, max_length=REASON_MAX)


class StageOwnerReassign(BaseModel):
    """جایگزینی مسئول یکی از سه مرحله روی یک پروندهٔ باز."""

    model_config = ConfigDict(str_strip_whitespace=True)

    stage_field: Literal["unit_supervisor_user_id", "deputy_user_id", "ceo_user_id"]
    new_user_id: int
    reason: str = Field(min_length=1, max_length=REASON_MAX)


class SubmissionExtension(BaseModel):
    """تمدیدِ مهلتِ ثبت برای یک پرونده.

    دلیل اجباری است: تمدیدِ بی‌دلیل، در بازبینی از تمدیدِ خودسرانه قابل تشخیص
    نیست. تاریخ هم اجباری است و نه یک «باز کن» — پرچمی که خودش را نمی‌بندد،
    مهلت را از اول بی‌معنا می‌کند.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    until: date
    reason: str = Field(min_length=1, max_length=REASON_MAX)


class EvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evaluation_code: str
    subject_personnel_id: int
    subject_full_name: str
    period_id: int | None
    unit_supervisor_user_id: int | None
    # None یعنی زنجیره معاونت ندارد و پرونده از HR مستقیم به مدیرعامل می‌رود.
    deputy_user_id: int | None
    ceo_user_id: int
    # مسئولِ HR این پرونده؛ null یعنی هنوز در صف مشترک منابع انسانی است
    hr_user_id: int | None = None
    hr_username: str | None = None
    status: EvaluationStatus
    general_score_pct: float | None
    specialized_score_pct: float | None
    final_weighted_pct: float | None
    recommendation: str | None
    # امتیاز ویژه جدا از امتیاز نهایی برگردانده می‌شود، نه در آن حل‌شده: هر جایی
    # که این عدد دیده می‌شود باید بشود پرسید «بابت چه؟»
    base_weighted_pct: float | None = None
    bonus_points: float | None = None
    bonus_reason: str | None = None
    evaluator_comment: str | None
    created_at: datetime
    finalized_at: datetime | None
    acknowledged_at: datetime | None = None
    # آیا این پرونده قبلاً حداقل یک‌بار برگشت خورده — تا صف بررسی بتواند آن را
    # از یک ثبت/تأیید تازه متمایز کند (روی list_evaluations پر می‌شود، نه اینجا)
    was_returned: bool = False
    # اعتراض کارمند روی نمای کامل هم دیده می‌شود، وگرنه HR جایی برای رسیدگی ندارد
    objection_at: datetime | None = None
    objection_reason: str | None = None
    objection_resolved_at: datetime | None = None
    objection_resolution: str | None = None

    # نمره‌دهندهٔ اول و تأییدکنندهٔ نهایی یک نفرند (کسی که مستقیم زیر نظر
    # مدیرعامل است). حالتی مجاز، ولی نه حالتی که باید پنهان بماند.
    single_decider: bool = False

    #: مهلتِ ثبت — تاریخِ پایانِ دوره، یا تمدیدی که منابع انسانی داده.
    #:
    #: روی نمای کامل هم هست چون ارزیاب باید *پیش از* رسیدن به دکمهٔ ثبت بداند تا
    #: کِی وقت دارد؛ فهمیدنش از پیامِ خطا یعنی مهلت را از دست داده.
    submission_deadline: date | None = None
    submission_deadline_extended: bool = False
    submission_extension_reason: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def stage(self) -> EvaluationStage | None:
        """None برای پروندهٔ لغوشده — در هیچ مرحله‌ای از زنجیره نیست."""
        return _STAGE_BY_STATUS.get(self.status)


class EvaluationDetail(EvaluationRead):
    scores: list[ScoreRead] = []
    comments: list[CommentRead] = []
    # خودارزیابی فقط برای HR کنار امتیاز ارزیاب دیده می‌شود تا فاصله‌ها مقایسه شوند.
    # عمداً در محاسبه نقشی ندارد — جدولش هم جداست (models/self_assessment.py).
    self_assessment: "SelfAssessmentRead | None" = None
    # شاخص‌های *این* پرونده و نسخهٔ چارچوبی که زیر آن باز شده (P1-05).
    #
    # بدون این، فرم از روی «شاخص‌های فعالِ امروز» ساخته می‌شد و همان خرابیِ
    # سمت سرور را در مرورگر تکرار می‌کرد: ارزیاب سؤالی را می‌دید که پرونده‌اش
    # نمی‌خواست، یا سؤالی را نمی‌دید که برای ثبت لازم بود.
    indicator_ids: list[int] = []
    indicator_framework_version: int | None = None


class EvaluationPage(BaseModel):
    total: int
    items: list[EvaluationRead]


class SpecialScoreUpdate(BaseModel):
    """امتیاز ویژه — نمرهٔ اختیاری بابت کاری خارج از شرح وظایف.

    صفر (با دلیل خالی) یعنی حذفش. سقفِ بالا این‌جا اعلام نمی‌شود چون از نسخهٔ
    طرحِ همان پرونده می‌آید؛ سرور آن را می‌سنجد.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    bonus_points: float = Field(ge=0, le=100)
    bonus_reason: str | None = Field(default=None, max_length=BONUS_REASON_MAX)


class EvaluatorCommentUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    evaluator_comment: str = Field(max_length=EVALUATOR_COMMENT_MAX)


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
    # کارمند حق دارد بداند امتیاز ویژه‌ای گرفته و بابت چه — بدون این، همان عدد
    # در نتیجه‌اش هست ولی توضیحش نیست.
    base_weighted_pct: float | None = None
    bonus_points: float | None = None
    bonus_reason: str | None = None
    recommendation: str | None
    finalized_at: datetime | None
    acknowledged_at: datetime | None
    # مسیر اعتراض: «رؤیت» فقط ثبت می‌کند که فرد نتیجه را دیده، نه این‌که پذیرفته.
    objection_at: datetime | None = None
    objection_reason: str | None = None
    objection_resolved_at: datetime | None = None
    objection_resolution: str | None = None


class MyEvaluationPage(BaseModel):
    total: int
    items: list[MyEvaluationRead]


class MyOpenEvaluation(BaseModel):
    """نمای «وضعیت‌فقط» از پروندهٔ در جریانِ خود کارمند.

    عمداً هیچ امتیاز، شواهد یا کامنتی ندارد: پرونده هنوز در حال تصمیم‌گیری است و
    نمرهٔ پیش‌نویس نه نهایی است نه قابل استناد. ولی این‌که «پرونده‌ای دربارهٔ من باز
    است و الان روی میز چه کسی است» چیزی است که فرد حق دارد بداند — بدون آن، فرایند
    از دید او یک جعبهٔ سیاه است که یک روز نتیجه‌اش اعلام می‌شود.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    evaluation_code: str
    status: EvaluationStatus
    created_at: datetime
    stage_entered_at: datetime
    # برای اینکه پس از رفرش، فرم یک‌بارمصرفِ خودارزیابی دوباره نمایش داده نشود.
    self_assessment_submitted_at: datetime | None = None
    #: شاخص‌های همین پرونده (P1-05) — فرم خودارزیابی باید از روی این ساخته شود،
    #: نه از «شاخص‌های فعالِ امروز». وگرنه کارمند به مجموعه‌ای پاسخ می‌دهد که
    #: ارزیاب به آن نمره نمی‌دهد، و مقایسهٔ دو دیدگاه بی‌معنا می‌شود.
    indicator_ids: list[int] = []
    #: آیا پنجرهٔ خودارزیابی هنوز باز است.
    #:
    #: سرور محاسبه‌اش می‌کند چون تعریفِ پنجره یک جا بیشتر نیست
    #: (`services/self_assessment.OPEN_STATUSES`). پیش از این فرانت فهرستِ
    #: وضعیت‌ها را دستی کپی کرده بود و می‌توانست از بک‌اند جدا بیفتد.
    #: سه شرط را با هم می‌سنجد: نقش خودارزیابی داشته باشد، پرونده در مرحلهٔ ثبت
    #: باشد، و مهلت نگذشته باشد.
    self_assessment_open: bool = False
    period_name: str | None = None
    period_ends_on: date | None = None
    #: مهلتِ *واقعیِ* ثبت. با `period_ends_on` یکی نیست: اگر منابع انسانی برای
    #: همین پرونده تمدید کرده باشد، این جلوتر است.
    submission_deadline: date | None = None
    submission_deadline_extended: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def stage_label(self) -> str:
        """برچسب فارسیِ «الان روی میز چه کسی است» برای نمایش مستقیم."""
        return _EMPLOYEE_STAGE_LABELS.get(self.status, "در جریان")


class SelfAssessmentInput(BaseModel):
    indicator_id: int
    score: int = Field(ge=1, le=5)
    note: str | None = Field(default=None, max_length=SELF_ASSESSMENT_NOTE_MAX)


class SelfAssessmentSubmit(BaseModel):
    """خودارزیابی کارمند — یک‌بار ثبت می‌شود و بعد قفل است.

    تغییرپذیر بودنش یعنی می‌شود بعد از دیدن نمرهٔ ارزیاب نظر خود را عوض کرد، که کل
    ارزش «دیدگاه مستقل» را از بین می‌برد.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    scores: list[SelfAssessmentInput]
    note: str | None = Field(default=None, max_length=SELF_ASSESSMENT_SUMMARY_MAX)


class SelfAssessmentScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    indicator_id: int
    score: int
    note: str | None


class SelfAssessmentRead(BaseModel):
    """نمای خودارزیابی — هم برای خودِ کارمند، هم کنار امتیاز ارزیاب برای زنجیره."""

    submitted_at: datetime | None
    note: str | None
    scores: list[SelfAssessmentScoreRead] = []


class CurrentSelfAssessmentRead(SelfAssessmentRead):
    """Self-assessment state for one personnel contract."""

    assessment_id: int | None = None
    personnel_id: int
    personnel_name: str
    contract_start_date: date
    contract_end_date: date
    state: str
    eligible: bool
    open: bool
    indicator_ids: list[int] = []


class MySelfAssessmentRead(SelfAssessmentRead):
    """نسخهٔ فقط‌خواندنی خودارزیابی‌های ثبت‌شدهٔ خود فرد."""

    assessment_id: int
    personnel_id: int
    contract_start_date: date
    contract_end_date: date


class ObjectionRequest(BaseModel):
    """اعتراض رسمی کارمند به نتیجهٔ نهایی."""

    model_config = ConfigDict(str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=OBJECTION_MAX)


class ObjectionResolution(BaseModel):
    """پاسخ منابع انسانی به اعتراض — اعتراضی که کسی جواب ندهد تشریفات است."""

    model_config = ConfigDict(str_strip_whitespace=True)

    resolution: str = Field(min_length=1, max_length=OBJECTION_MAX)
