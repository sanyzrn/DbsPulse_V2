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
    # پرسنل فعالی که زنجیرهٔ ارزیابی ندارند. تا امروز این‌ها از *مخرج* حذف
    # می‌شدند، پس پوشش می‌توانست ۱۰۰٪ نشان بدهد در حالی که کسی ارزیابی‌شان
    # نکرده. حالا یک شکافِ دیده‌شدنی‌اند، نه یک حذفِ خاموش.
    without_chain_total: int = 0
    without_chain: list[NotStartedPersonnel] = []


class BulkCreateRequest(BaseModel):
    """تعریف کوهورتی که برایش ارزیابی ساخته می‌شود (P2-03).

    همهٔ فیلدها اختیاری‌اند و خالی یعنی «همه». پرسنل غیرفعال عمداً فیلتر نمی‌شود:
    اگر بی‌صدا کنار گذاشته شود، HR هرگز نمی‌فهمد چرا کسی در فهرست نیست — به‌جایش
    در نتیجه با دلیل خودش می‌آید.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    org_unit: str | None = None
    #: True فقط مدیران، False فقط غیرمدیران، None هر دو
    only_managers: bool | None = None
    contract_ends_before: date | None = None


class BulkPersonResult(BaseModel):
    personnel_id: int
    full_name: str
    org_unit: str
    #: created / skipped_already_open / blocked_*
    outcome: str
    #: همان نتیجه به فارسی، برای نمایش مستقیم
    reason: str
    evaluation_id: int | None = None
    evaluation_code: str | None = None


class BulkCreateResult(BaseModel):
    """نتیجهٔ پیش‌نمایش یا اجرا — شکلشان عمداً یکی است.

    اگر پیش‌نمایش و اجرا پاسخ‌های متفاوتی می‌دادند، UI دو مسیر رندر جدا لازم
    داشت و همان‌جاست که وعدهٔ پیش‌نمایش از نتیجهٔ اجرا جدا می‌شود.
    """

    #: True یعنی چیزی نوشته نشده است
    dry_run: bool
    total: int
    counts: dict[str, int]
    results: list[BulkPersonResult]
