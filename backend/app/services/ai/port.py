"""لایهٔ ۱ — قرارداد «از مدل بپرس».

هرچه بالاتر از این لایه است به *این* وابسته است، نه به HTTP. یعنی می‌شود کل
مسیرِ گفت‌وگو را با یک آداپتور قلابی تست کرد بدون اینکه هیچ درخواستی به بیرون
برود — و همان تستی که ثابت می‌کند دکمهٔ واقعیِ رابط واقعاً به آداپتور می‌رسد.

`available` یک حالت است نه یک استثنا: هر جایی که دکمهٔ دستیار را نشان می‌دهد
اول همین را می‌پرسد و اگر خاموش بود دکمه را اصلاً نمی‌سازد. دکمه‌ای که تنها
پاسخش «در دسترس نیست» باشد، از نبودنِ دکمه بدتر است.
"""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    #: فقط برای role="assistant" با فراخوانیِ ابزار: ابزارهایی که مدل خواسته.
    tool_calls: tuple["ToolCall", ...] = ()
    #: فقط برای role="tool": کدام فراخوانی، نتیجهٔ این پیام است.
    tool_call_id: str = ""

    def to_wire(self) -> dict:
        """شکلِ HTTPِ این پیام — یک‌جا تا آداپتور نگرانِ جزئیات نباشد."""
        if self.role == "assistant" and self.tool_calls:
            message: dict = {
                "role": "assistant",
                "content": self.content or None,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": call.arguments_json},
                    }
                    for call in self.tool_calls
                ],
            }
            return message
        if self.role == "tool":
            return {
                "role": "tool",
                "tool_call_id": self.tool_call_id,
                "content": self.content,
            }
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class ToolCall:
    """خواستهٔ مدل برای صدا زدن یک ابزار."""

    id: str
    name: str
    arguments_json: str


@dataclass(frozen=True)
class ChatResponse:
    content: str
    #: ابزارهایی که مدل در همین پاسخ خواسته است — تهی یعنی «جوابِ نهایی».
    tool_calls: tuple[ToolCall, ...] = ()
    #: چیزی که برای نمایش «چقدر خرج شد» لازم است. سرویس‌ها همیشه نمی‌دهند.
    usage: dict = field(default_factory=dict)


class AiUnavailable(Exception):
    """دستیار پیکربندی نشده — سه حالتِ متفاوت که به کاربر یکی به نظر می‌رسند:
    «راه‌اندازی نشده»، «راه‌اندازی شده و خطا می‌دهد»، «کار می‌کند».
    این استثنا فقط اولی است."""


class AiRequestFailed(Exception):
    """سرویس جواب داد ولی جوابش خطا بود.

    متنِ خودِ سرویس در `detail` می‌نشیند و بی‌کم‌وکاست به کاربر نشان داده
    می‌شود: تفاوتِ ۴۰۱ با «مدل پیدا نشد» چهار رفعِ متفاوت است و کاربر روی سه
    تای آن می‌تواند کاری بکند. «مشکلی پیش آمد» هیچ‌کدام را نمی‌گوید.
    """

    def __init__(self, detail: str, status_code: int | None = None) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class ToolProtocolUnsupported(AiRequestFailed):
    """سرویس شِمای ابزار را نمی‌پذیرد — حلقه به پروتکلِ JSON می‌افتد."""


class ChatAdapter(Protocol):
    @property
    def available(self) -> bool: ...

    async def send(
        self, messages: list[ChatMessage], *, tools: list[dict] | None = None
    ) -> ChatResponse: ...
