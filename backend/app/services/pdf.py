import base64
import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path

import jdatetime
import qrcode
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_jalali(value: str | datetime | None) -> str:
    """تاریخ ISO میلادی یا شیء datetime → تاریخ شمسی با ارقام فارسی برای سند رسمی؛
    مقدار نامعتبر دست‌نخورده برمی‌گردد تا snapshot های قدیمی هم رندر شوند."""
    if not value:
        return "—"
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return str(value)
    jalali = jdatetime.datetime.fromgregorian(datetime=dt)
    return jalali.strftime("%Y/%m/%d ساعت %H:%M").translate(_PERSIAN_DIGITS)


def qr_data_uri(payload: str) -> str:
    """QR را به‌صورت data URI (PNG base64) برمی‌گرداند تا مستقیماً در قالب تعبیه شود
    (بدون درخواست شبکه/فایل خارجی)."""
    img = qrcode.make(payload)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


# autoescape اجباری است: متن شواهد/کامنت‌ها ورودی کاربر است و نباید به‌صورت HTML خام
# وارد سند رسمی شود (جعل محتوا یا حمله file:// از طریق WeasyPrint).
_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
)
_env.filters["jalali"] = to_jalali

_TEMPLATES_URI_PREFIX = _TEMPLATES_DIR.as_uri() + "/"

# Try importing WeasyPrint; if it fails (missing native libs), PDF generation
# will be unavailable but the rest of the app stays fully functional.
_weasyprint_available = False
_WeasyPrintHTML = None
_default_url_fetcher = None
try:
    from weasyprint import HTML as _WeasyPrintHTML
    from weasyprint import default_url_fetcher

    _default_url_fetcher = default_url_fetcher
    _weasyprint_available = True
except (OSError, ImportError):
    # OSError: پکیج نصب است ولی کتابخانه‌های بومی (Pango/Cairo/GDK-PixBuf) نیستند.
    # ImportError: خود پکیج نصب نشده. در هر دو حالت اپ سالم بالا می‌آید و فقط چاپ PDF
    # غیرفعال می‌شود؛ endpoint خروجی PDF با پیام واضح ۵۰۰ می‌دهد (نه خطای مبهم).
    logger.warning(
        "WeasyPrint native libraries (Pango/Cairo/GDK-PixBuf) not found. "
        "PDF generation will be unavailable until those are installed. "
        "All other features work normally."
    )


def weasyprint_available() -> bool:
    return _weasyprint_available


def _local_templates_only_url_fetcher(url: str, *args, **kwargs):
    """فقط فایل‌های داخل پوشه templates (فونت‌ها) و data URI های خودبسنده مجازند؛
    هر URL دیگری — از جمله file:// به مسیرهای دیگر یا http(s) — مسدود می‌شود تا PDF
    نتواند منبع خارجی بخواند. data URI امن است چون هیچ منبعی را واکشی نمی‌کند."""
    if url.startswith("data:"):
        return _default_url_fetcher(url, *args, **kwargs)
    if not url.startswith(_TEMPLATES_URI_PREFIX):
        raise ValueError(f"دسترسی به منبع خارج از پوشه templates مسدود شد: {url}")
    return _default_url_fetcher(url, *args, **kwargs)


def render_evaluation_summary_pdf(
    snapshot: dict, verify_url: str | None = None
) -> bytes:
    if not _weasyprint_available:
        raise RuntimeError(
            "WeasyPrint is not available (missing GTK/GObject native libraries). "
            "Install them to enable PDF generation."
        )
    template = _env.get_template("evaluation_summary.html")
    html = template.render(
        snapshot=snapshot,
        verify_url=verify_url,
        verify_qr=qr_data_uri(verify_url) if verify_url else None,
    )
    return _WeasyPrintHTML(
        string=html,
        base_url=str(_TEMPLATES_DIR),
        url_fetcher=_local_templates_only_url_fetcher,
    ).write_pdf()
