from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import PersonnelStatus, SeparationReason
from app.schemas.user import _PASSWORD_MIN_LENGTH, _USERNAME_PATTERN


class PersonnelBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    personnel_code: str = Field(min_length=1, max_length=50)
    full_name: str = Field(min_length=1, max_length=200)
    job_title: str = Field(min_length=1, max_length=150)
    is_manager: bool = False
    org_unit: str = Field(min_length=1, max_length=150)
    contract_start_date: date
    contract_end_date: date


class PersonnelAccountCreate(BaseModel):
    """حساب کاربری «کارمند» که هم‌زمان با خودِ پرسنل ساخته می‌شود.

    نقش عمداً در ورودی نیست: این مسیر دقیقاً برای این وجود دارد که فرد بتواند
    کارنامهٔ خودش را ببیند، پس همیشه employee است. نقش‌های زنجیرهٔ تأیید از مسیر
    مدیریت کاربران ساخته می‌شوند.

    قواعد نام کاربری و رمز از schemas/user.py می‌آیند تا یک سیاست بیشتر نداشته باشیم.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(pattern=_USERNAME_PATTERN)
    password: str = Field(min_length=_PASSWORD_MIN_LENGTH)


class PersonnelCreate(PersonnelBase):
    # اختیاری و نه خودکار: هر پرسنلی لازم نیست حساب داشته باشد (خط تولید، پیمانکار،
    # کسی که اصلاً با سامانه کار نمی‌کند). ساختن خودکارِ حسابی که هیچ‌وقت استفاده
    # نمی‌شود یعنی انباشتن حساب‌های خفته با رمز موقتِ تغییرنکرده — همان دسته مشکلی
    # که فاز ۰ تازه پاکش کرد.
    account: PersonnelAccountCreate | None = None

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
    # فقط هنگام غیرفعال‌کردن معنا دارند. اگر علت داده نشود و وضعیت به «غیرفعال»
    # برود، سرور رد می‌کند — نه چون فیلد اجباری است، بلکه چون رفتنِ بدونِ علت
    # همان چیزی است که این دو ستون برای حذفش آمدند.
    separation_reason: SeparationReason | None = None
    separation_date: date | None = None


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
    separation_date: date | None = None
    separation_reason: SeparationReason | None = None
    created_at: datetime
    updated_at: datetime


class PersonnelCreated(PersonnelRead):
    """پاسخ ساخت پرسنل — ابرمجموعهٔ PersonnelRead.

    نام کاربریِ ساخته‌شده برگردانده می‌شود تا UI بتواند صریح تأیید کند «حساب هم
    ساخته شد»؛ بدون آن، HR نمی‌داند تیک زدنش اثری داشته یا نه.
    """

    account_username: str | None = None


class PersonnelPage(BaseModel):
    total: int
    items: list[PersonnelRead]


# ───────────────────────────── ورود دسته‌ای از Excel


class ImportRowIssue(BaseModel):
    """یک ردیف فایل به‌همراه وضعیتش — چه سالم چه خطادار.

    ردیف‌های خطادار هم برگردانده می‌شوند، نه فقط شمارششان: کاربر باید بداند کدام
    ردیف و دقیقاً چرا، وگرنه باید کل فایل را خودش بگردد.
    """

    row_number: int
    personnel_code: str
    full_name: str
    username: str | None = None
    errors: list[str] = []


class PersonnelImportPreview(BaseModel):
    total_rows: int
    valid_count: int
    invalid_count: int
    accounts_to_create: int
    rows: list[ImportRowIssue]
    file_errors: list[str] = []


class CreatedAccount(BaseModel):
    """رمز موقت فقط همین یک بار برگردانده می‌شود؛ ذخیره نمی‌شود و در لاگ نمی‌رود."""

    personnel_code: str
    full_name: str
    username: str
    temporary_password: str


class PersonnelImportResult(BaseModel):
    created_personnel: int
    created_accounts: int
    skipped_rows: int
    accounts: list[CreatedAccount] = []
