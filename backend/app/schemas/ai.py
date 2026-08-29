from datetime import datetime

from pydantic import BaseModel, Field


class AiProviderOption(BaseModel):
    """یک سرویسِ آماده. فرم از روی همین‌ها ساخته می‌شود و نه از فهرستی در فرانت‌اند —
    دو نسخه از این جدول یعنی روزی که آدرسی عوض شود و یکی از آن دو نداند."""

    id: str
    label: str
    base_url: str
    default_model: str
    note: str


class AiSettingsRead(BaseModel):
    enabled: bool
    provider: str
    #: فهرست سرویس‌های آماده، برای ساختن دکمه‌های انتخاب.
    providers: list[AiProviderOption]
    base_url: str
    model: str
    #: هرگز خودِ کلید — فقط چهار نویسهٔ آخر، تا آدم بشناسدش.
    api_key_hint: str
    api_key_configured: bool
    temperature: int
    max_tokens: int
    timeout_seconds: int
    instructions: str
    restrict_to_platform: bool
    context_record_limit: int
    allow_write_actions: bool
    max_user_chars: int
    #: عمقِ حلقهٔ ابزار در یک نوبت — یعنی دستیار چند پله می‌تواند کار کند.
    max_tool_iterations: int
    allow_uploads: bool
    max_upload_mb: int


class AiSettingsUpdate(BaseModel):
    enabled: bool | None = None
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    #: `None` یعنی دست نزن، رشتهٔ خالی یعنی پاکش کن.
    api_key: str | None = None
    temperature: int | None = Field(default=None, ge=0, le=100)
    max_tokens: int | None = Field(default=None, ge=100, le=32000)
    timeout_seconds: int | None = Field(default=None, ge=5, le=300)
    instructions: str | None = None
    restrict_to_platform: bool | None = None
    context_record_limit: int | None = Field(default=None, ge=0, le=200)
    allow_write_actions: bool | None = None
    max_user_chars: int | None = Field(default=None, ge=200, le=20000)
    max_tool_iterations: int | None = Field(default=None, ge=1, le=12)
    allow_uploads: bool | None = None
    max_upload_mb: int | None = Field(default=None, ge=1, le=20)


class AiUserAccessRead(BaseModel):
    user_id: int
    username: str
    display_name: str
    role: str
    enabled: bool
    api_key_hint: str
    api_key_configured: bool
    model: str
    allow_write_actions: bool
    daily_message_limit: int


class AiUserAccessUpdate(BaseModel):
    enabled: bool | None = None
    api_key: str | None = None
    model: str | None = None
    allow_write_actions: bool | None = None
    daily_message_limit: int | None = Field(default=None, ge=0, le=1000)


class AiStatus(BaseModel):
    """سه حالتی که در کد یکی به‌نظر می‌رسند و برای کاربر کاملاً فرق دارند."""

    #: آیا این کاربر اصلاً دستیار می‌بیند
    available: bool
    #: اگر نه، چرا — به زبان قابل‌اقدام
    reason: str
    allow_write_actions: bool
    #: بارگذاری فایل برای این کاربر ممکن است یا نه
    allow_uploads: bool = False


class AiStepRead(BaseModel):
    """ردِ یک فراخوانیِ ابزار در نوبتِ دستیار — «چه کاری انجام شد»."""

    tool: str
    status: str
    summary: str = ""
    detail: dict = Field(default_factory=dict)


class AiPendingActionRead(BaseModel):
    """کنشِ در انتظارِ تأیید — کارتِ رابط مستقیماً از همین ساخته می‌شود."""

    id: int
    tool: str
    summary: str
    arguments: dict = Field(default_factory=dict)
    status: str = "pending"
    result_text: str = ""
    expires_at: datetime | None = None


class AiUploadRead(BaseModel):
    id: int
    filename: str
    kind: str = "file"
    size_bytes: int = 0
    total_rows: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    committed: bool = False
    note: str = ""


class AiMessageRead(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    #: سازگاری با رابط‌های قدیمی — کنش‌ها حالا در `pending` زندگی می‌کنند.
    actions: list[AiPendingActionRead] = []
    steps: list[AiStepRead] = []
    pending: list[AiPendingActionRead] = []


class AiChatRequest(BaseModel):
    conversation_id: int | None = None
    message: str


class AiChatResponse(BaseModel):
    conversation_id: int
    reply: str
    steps: list[AiStepRead] = []
    pending: list[AiPendingActionRead] = []
    usage: dict = Field(default_factory=dict)


class AiPendingDecisionRequest(BaseModel):
    """تأیید یا رد — بدنهٔ خالی؛ همهٔ هویت از مسیر می‌آید."""


class AiConversationRead(BaseModel):
    id: int
    title: str
    updated_at: datetime


class AiConversationRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class AiToolRead(BaseModel):
    """ابزاری که *این* کاربر واقعاً دارد — برای پیشنهادهای رابط و شفافیت."""

    name: str
    description: str
    category: str
    read_only: bool
    risky: bool


class AiTestRequest(BaseModel):
    """آزمودنِ اتصال با مقدارهایی که هنوز ذخیره نشده‌اند."""

    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None


class AiTestResult(BaseModel):
    ok: bool
    #: جملهٔ خودِ سرویس، نه ترجمهٔ ما.
    detail: str
