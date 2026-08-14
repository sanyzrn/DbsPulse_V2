"""ترجمهٔ خطاهای اعتبارسنجی به یک جملهٔ فارسی (P2-05).

FastAPI برای خطای اعتبارسنجی، `detail` را به‌صورت *آرایه‌ای* از دیکشنری‌های
انگلیسی برمی‌گرداند:

    {"detail": [{"type": "string_too_long", "loc": ["body", "reason"], "msg":
     "String should have at most 1000 characters", ...}]}

فرانت‌اند `extractErrorMessage` فقط رشته (یا دیکشنریِ دارای message) را می‌فهمد،
پس همهٔ این خطاها روی صفحه به «خطایی غیرمنتظره رخ داد» تبدیل می‌شدند — یعنی
کاربری که ۳۰۰۰ نویسه شواهد نوشته، هیچ‌وقت نمی‌فهمید مشکل *طول* بوده و چقدر باید
کم کند. سقف گذاشتن بدون پیام، ویژگی نیست؛ بن‌بست است.

این‌جا همان آرایه به یک جملهٔ فارسی تبدیل می‌شود و ساختار کامل زیر
`detail_items` باقی می‌ماند تا اگر روزی UI بخواهد خطا را کنار خودِ فیلد نشان
دهد، اطلاعات از دست نرفته باشد.
"""
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# نام فارسی فیلدهایی که کاربر واقعاً در فرم می‌بیند. هرچه این‌جا نباشد با نام
# انگلیسی خودش نشان داده می‌شود — دیدنِ `evidence_text` بهتر از «یک فیلد» است.
FIELD_LABELS: dict[str, str] = {
    "comment_text": "متن دیدگاه",
    "evidence_text": "شواهد",
    "evaluator_comment": "جمع‌بندی ارزیاب",
    "reason": "دلیل",
    "resolution": "پاسخ",
    "note": "یادداشت",
    "summary": "شرح",
    "title": "عنوان",
    "description": "شرح",
    "category": "دسته",
    "score": "امتیاز",
    "new_password": "رمز عبور جدید",
    "username": "نام کاربری",
    "full_name": "نام و نام خانوادگی",
    "national_id": "کد ملی",
    "org_unit": "واحد سازمانی",
    "job_title": "عنوان شغلی",
}


def _field_name(loc: tuple) -> str:
    """آخرین بخشِ رشته‌ایِ مسیر خطا — اندیس‌های عددی (مثلاً scores.3.score) کنار
    می‌روند چون شمارهٔ ردیف برای کاربر معنایی ندارد."""
    for part in reversed(loc):
        if isinstance(part, str) and part not in ("body", "query", "path"):
            return FIELD_LABELS.get(part, part)
    return "ورودی"


def _describe(error: dict) -> str:
    field = _field_name(tuple(error.get("loc", ())))
    kind = error.get("type", "")
    ctx = error.get("ctx") or {}

    if kind == "string_too_long":
        limit = ctx.get("max_length")
        return f"«{field}» طولانی‌تر از حد مجاز است (حداکثر {limit} نویسه)"
    if kind == "string_too_short":
        # min_length=1 در عمل یعنی «خالی نگذارید»، نه «حداقل ۱ نویسه بنویسید»
        if ctx.get("min_length") == 1:
            return f"«{field}» را خالی نگذارید"
        return f"«{field}» کوتاه‌تر از حد مجاز است (حداقل {ctx.get('min_length')} نویسه)"
    if kind in ("missing", "value_error.missing"):
        return f"«{field}» الزامی است"
    if kind in ("greater_than_equal", "less_than_equal", "greater_than", "less_than"):
        bound = ctx.get("ge", ctx.get("le", ctx.get("gt", ctx.get("lt"))))
        return f"مقدار «{field}» خارج از بازهٔ مجاز است (مرز: {bound})"
    if kind.startswith("int") or kind.startswith("float") or kind.startswith("decimal"):
        return f"«{field}» باید عدد باشد"
    if kind.startswith("date"):
        return f"«{field}» تاریخ معتبری نیست"
    if kind == "enum":
        return f"مقدار «{field}» مجاز نیست"
    return f"مقدار «{field}» معتبر نیست"


def persian_validation_message(errors: list[dict]) -> str:
    """چند خطا با «؛» به هم وصل می‌شوند — کاربر باید همهٔ ایرادها را یک‌جا ببیند،
    نه اینکه هر بار یکی را رفع کند و به بعدی بخورد."""
    if not errors:
        return "ورودی نامعتبر است"
    seen: list[str] = []
    for error in errors:
        message = _describe(error)
        if message not in seen:
            seen.append(message)
    return "؛ ".join(seen)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": persian_validation_message(exc.errors()),
            # ساختار اصلی حفظ می‌شود: بدون آن، UI هرگز نمی‌تواند خطا را به فیلد
            # مربوطه بچسباند، و ابزارهای بیرونی هم نوعِ خطا را از دست می‌دهند.
            "detail_items": [
                {"field": _field_name(tuple(e.get("loc", ()))), "type": e.get("type", "")}
                for e in exc.errors()
            ],
        },
    )
