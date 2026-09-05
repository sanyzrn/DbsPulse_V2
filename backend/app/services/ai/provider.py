"""لایهٔ ۲ — آداپتور یک سرویسِ سازگار با OpenAI.

هیچ‌چیزِ این فایل دربارهٔ ارزیابی عملکرد نمی‌داند؛ فقط پیام می‌گیرد و متن
برمی‌گرداند.
"""
import httpx

from app.services.ai.port import AiRequestFailed, AiUnavailable, ChatMessage, ChatResponse


class OpenAiCompatibleAdapter:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 60,
        temperature: float = 0.3,
        max_tokens: int = 1200,
    ) -> None:
        self._base_url = (base_url or "").rstrip("/")
        self._api_key = api_key or ""
        self._model = model or ""
        self._timeout = max(5, timeout_seconds)
        self._temperature = temperature
        self._max_tokens = max_tokens

    @property
    def available(self) -> bool:
        return bool(self._base_url and self._api_key and self._model)

    async def send(self, messages: list[ChatMessage]) -> ChatResponse:
        if not self.available:
            raise AiUnavailable("دستیار هوشمند هنوز پیکربندی نشده است")

        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        url = f"{self._base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
        except httpx.TimeoutException:
            # بدون این پیام، درخواستِ گیرکرده از مدلِ کُند قابل تشخیص نیست.
            raise AiRequestFailed(
                f"سرویس در {self._timeout} ثانیه پاسخ نداد. آدرس سرویس یا اتصال شبکه را بررسی کنید."
            ) from None
        except httpx.HTTPError as err:
            # متنِ خودِ کتابخانه می‌ماند: «نام میزبان پیدا نشد» و «اتصال رد شد»
            # دو رفعِ متفاوت‌اند.
            raise AiRequestFailed(f"اتصال به سرویس ممکن نشد: {err}") from None

        if response.status_code >= 400:
            raise AiRequestFailed(_error_text(response), response.status_code)

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise AiRequestFailed(
                "پاسخ سرویس قابل خواندن نبود. معمولاً یعنی آدرس سرویس به یک نقطهٔ "
                f"پایانیِ سازگار با OpenAI اشاره نمی‌کند. پاسخ: {response.text[:200]}"
            ) from None

        return ChatResponse(content=content or "", usage=body.get("usage") or {})


def _error_text(response: httpx.Response) -> str:
    """جملهٔ خودِ سرویس، نه ترجمهٔ ما.

    نیمی از مشکلات راه‌اندازی «نام مدل اشتباه» است و تنها کسی که این را
    می‌داند خودِ سرویس است.
    """
    try:
        body = response.json()
        message = body.get("error", {}).get("message") or body.get("message")
        if message:
            return f"{response.status_code}: {message}"
    except ValueError:
        pass
    return f"{response.status_code}: {response.text[:300] or 'بدون توضیح'}"
