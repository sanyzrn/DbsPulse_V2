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


class AiActionRead(BaseModel):
    name: str
    summary: str
    payload: dict


class AiMessageRead(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    actions: list[AiActionRead] = []


class AiChatRequest(BaseModel):
    conversation_id: int | None = None
    message: str


class AiChatResponse(BaseModel):
    conversation_id: int
    reply: str
    actions: list[AiActionRead] = []


class AiRunActionRequest(BaseModel):
    conversation_id: int
    name: str
    payload: dict


class AiRunActionResponse(BaseModel):
    result: str


class AiConversationRead(BaseModel):
    id: int
    title: str
    updated_at: datetime


class AiTestRequest(BaseModel):
    """آزمودنِ اتصال با مقدارهایی که هنوز ذخیره نشده‌اند."""

    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None


class AiTestResult(BaseModel):
    ok: bool
    #: جملهٔ خودِ سرویس، نه ترجمهٔ ما.
    detail: str
