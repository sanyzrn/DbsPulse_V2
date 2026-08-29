"""سرویسِ قلابیِ سازگار با OpenAI برای آزمونِ سرتسری.

سناریوسازی از روی *نتیجهٔ ابزارها* می‌خواند نه از متنِ پیام‌ها: هر بار که
نتیجهٔ بازرسی خطا دارد، تاریخ می‌پرسد؛ بعد از پاسخِ کاربر اصلاح می‌کند؛
بعد از اصلاحِ سالم، پیشنهادِ ورود می‌دهد. رفتارِ قابلِ پیش‌بینی برای
مرورگرِ خودکار.
"""
import json
import re

from fastapi import FastAPI, Request

app = FastAPI(title="Mock LLM")

# وضعیتِ گفت‌وگو در حافظهٔ خودِ سرویس — آزمونِ تک‌کاربره است.
STATE: dict = {"last_tool": None, "last_upload_id": None, "last_invalid": None}


def _tool_results(messages: list[dict]) -> list[dict]:
    out = []
    for message in messages:
        if message.get("role") == "tool":
            try:
                out.append(json.loads(message.get("content") or "{}"))
            except ValueError:
                continue
    return out


def _reply(content: str, calls: list[dict] | None = None) -> dict:
    message: dict = {"role": "assistant", "content": content or None}
    if calls:
        message["tool_calls"] = calls
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": 1,
        "model": "mock-1",
        "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls" if calls else "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    }


def _tool(name: str, call_id: str, arguments: dict) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
    }


def _upload_id(messages: list[dict]) -> int:
    for message in messages:
        content = message.get("content") or ""
        match = re.search(r"فایل #(\d+)", content)
        if match:
            return int(match.group(1))
    return 1


_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _jalali(value: str) -> str | None:
    match = re.search(r"(1[34]\d\d)[/٫.](\d{1,2})[/٫.](\d{1,2})", value.translate(_DIGITS))
    if match:
        return f"{match.group(1)}/{int(match.group(2))}/{int(match.group(3))}"
    return None


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> dict:
    body = await request.json()
    messages = body.get("messages", [])
    last = messages[-1] if messages else {}
    last_content = last.get("content") or ""

    # ── نتیجهٔ ابزار: ادامه بر اساس آنچه واقعاً دیدیم ────────────────────
    if last.get("role") == "tool":
        try:
            payload = json.loads(last_content)
        except ValueError:
            payload = {}
        if "total_rows" in payload and "rows" in payload:
            STATE["last_tool"] = "inspect"
            STATE["last_upload_id"] = payload.get("upload_id")
            STATE["last_invalid"] = payload["invalid_count"]
            bad = next((r for r in payload["rows"] if r.get("errors")), None)
            STATE["last_row"] = bad["row_number"] if bad else 2
        elif payload.get("patched"):
            STATE["last_tool"] = "patch"
            STATE["last_upload_id"] = payload.get("upload_id")
        elif payload.get("ready_for_confirmation"):
            STATE["last_tool"] = "propose_import"

        if "total_rows" in payload and "rows" in payload:  # inspect_upload
            if payload["invalid_count"] > 0:
                row = payload["rows"][0]
                return _reply(
                    f"فایل «{payload.get('filename', '')}» را دیدم: {payload['total_rows']} ردیف دارد، "
                    f"{payload['valid_count']} سالم و {payload['invalid_count']} خطادار.\n\n"
                    f"**ردیف {row['row_number']} ({row.get('full_name') or 'بی‌نام'})**: "
                    + "؛ ".join(row.get("errors", []))
                    + "\n\nلطفاً مقدار درست را بگویید (مثلاً پایان قرارداد را ۱۴۰۶/۰۶/۰۱)."
                )
            if payload["invalid_count"] == 0 and payload["valid_count"] > 0:
                return _reply(
                    f"همهٔ {payload['valid_count']} ردیف سالم‌اند. بگویید «وارد کن» تا پیشنهاد ورود را ثبت کنم."
                )

        if payload.get("patched"):  # patch_upload_rows
            return _reply(
                f"{payload['patched']} سلول اصلاح شد؛ حالا {payload['valid_count']} ردیف سالم است. "
                "بگویید «وارد کن» تا پیشنهاد ورود را ثبت کنم."
            )

        if payload.get("ready_for_confirmation"):  # import_personnel (پیشنهاد)
            return _reply(
                f"پیشنهاد ورود {payload['valid_rows']} ردیف ثبت شد. کارتِ تأیید را می‌بینید؛ "
                "با پذیرفتن، پرسنل و زنجیره و حساب‌ها ساخته می‌شوند."
            )

        if payload.get("contracts") is not None:  # expiring_contracts
            return _reply(f"{payload['count']} قراردادِ رو به اتمام پیدا شد.")

        if "total_evaluations" in payload:  # report_summary
            return _reply(f"گزارش: {payload['total_evaluations']} ارزیابی نهایی‌شده؛ میانگین {payload.get('avg_final_pct')}.")

        if "count" in payload and "evaluations" in payload:  # search_evaluations
            return _reply(f"{payload['count']} پرونده در دامنهٔ دسترسی شما پیدا شد.")

        if payload.get("status") == "awaiting_confirmation":
            return _reply("منتظر تأیید شما هستم.")

        if payload.get("matches") is not None:  # search_personnel
            return _reply(f"{payload['matches']} نفر مطابق جست‌وجو پیدا شد.")

        return _reply("انجام شد.")

    # ── پیامِ کاربر: سناریو را شروع کن ────────────────────────────────────
    user_text = last_content
    upload_id = _upload_id(messages)
    state_tool = STATE.get("last_tool")

    if "اکسل" in user_text or "فایل" in user_text or "وارد" in user_text:
        if state_tool == "patch" and STATE.get("last_upload_id"):
            return _reply("پیشنهاد را ثبت می‌کنم.", calls=[_tool("import_personnel", "c_imp", {"upload_id": STATE["last_upload_id"]})])
        if state_tool == "inspect" and STATE.get("last_invalid") == 0 and STATE.get("last_upload_id"):
            return _reply("پیشنهاد را ثبت می‌کنم.", calls=[_tool("import_personnel", "c_imp", {"upload_id": STATE["last_upload_id"]})])
        if state_tool == "inspect":
            return _reply("وضعیت تازه را می‌گیرم.", calls=[_tool("inspect_upload", "c_ins2", {"upload_id": upload_id})])
        return _reply("بازرسی می‌کنم.", calls=[_tool("inspect_upload", "c_ins", {"upload_id": upload_id})])

    jalali = _jalali(user_text)
    if jalali:
        target = STATE.get("last_upload_id") or upload_id
        return _reply(
            "درست می‌کنم.",
            calls=[_tool("patch_upload_rows", "c_patch", {
                "upload_id": target,
                "edits": [{"row_number": STATE.get("last_row", 2), "fields": {"پایان قرارداد": jalali}}],
            })],
        )

    if "قرارداد" in user_text:
        return _reply("می‌خوانم.", calls=[_tool("expiring_contracts", "c_exp", {"days": 120})])

    if "میانگین" in user_text or "گزارش" in user_text:
        return _reply("بگیرم.", calls=[_tool("report_summary", "c_rep", {})])

    if "پرونده" in user_text or "ارزیابی" in user_text:
        return _reply("جست‌وجو می‌کنم.", calls=[_tool("search_evaluations", "c_sev", {})])

    if "پرسنل" in user_text:
        return _reply("جست‌وجو می‌کنم.", calls=[_tool("search_personnel", "c_sp", {"q": ""})])

    return _reply("سلام! من همکار DbsPulse هستم. چه کاری برایتان انجام بدهم؟ (پاسخِ آزمونِ سرویسِ قلابی)")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8100, log_level="warning")
