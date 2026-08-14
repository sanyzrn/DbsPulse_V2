"""ثابت‌های استقرار که نمی‌شود با اجرای برنامه سنجیدشان.

این فایل‌ها بیرون از فرایند پایتون اجرا می‌شوند (nginx، compose)، پس تست معمولی
لمسشان نمی‌کند — ولی چند اشتباهِ مشخص در آن‌ها هزینهٔ واقعی دارد و با خواندن خودِ
فایل قابل جلوگیری است.
"""
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_NGINX_TEMPLATE = _REPO_ROOT / "frontend" / "nginx" / "default.conf.template"


@pytest.fixture(scope="module")
def nginx_conf() -> str:
    """*دستورهای* قالب، بدون توضیحات.

    توضیحات این فایل عمداً دربارهٔ همان چیزهایی حرف می‌زنند که این تست‌ها ممنوع
    می‌کنند (چرا `preload` نیست، چرا `$proxy_add_x_forwarded_for` نیست). اگر متن
    خام را بسنجیم، خودِ توضیحِ درست باعث شکست تست می‌شود.
    """
    if not _NGINX_TEMPLATE.exists():
        pytest.skip("قالب nginx در این چیدمان وجود ندارد")
    raw = _NGINX_TEMPLATE.read_text(encoding="utf-8")
    return "\n".join(
        line for line in raw.splitlines() if not line.strip().startswith("#")
    )


def test_hsts_is_sent(nginx_conf: str):
    assert "Strict-Transport-Security" in nginx_conf


def test_hsts_is_never_emitted_unconditionally(nginx_conf: str):
    """خطرِ مشخص: فرستادن HSTS روی HTTP.

    مرورگر همان نام میزبان را برای مدت max-age به HTTPS سنجاق می‌کند. اگر این هدر
    بی‌قید فرستاده شود، یک استقرار داخلی/توسعه که عمداً HTTP است از دسترس خارج
    می‌شود و برگرداندنش دست ما نیست — باید منتظر انقضای max-age در مرورگرِ هر
    کاربر ماند. پس مقدار هدر باید از یک متغیر بیاید که فقط روی https پر می‌شود.
    """
    for line in nginx_conf.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "Strict-Transport-Security" not in stripped:
            continue
        if not stripped.startswith("add_header"):
            continue
        assert re.search(r"add_header\s+Strict-Transport-Security\s+\$", stripped), (
            f"HSTS باید از متغیر شرطی بیاید، نه مقدار ثابت: {stripped}"
        )


def test_the_hsts_variable_is_empty_for_plain_http(nginx_conf: str):
    """نگاشت باید پیش‌فرضِ خالی داشته باشد؛ nginx هدر با مقدار خالی را اضافه نمی‌کند."""
    mapping = re.search(r"map\s+\$\w+\s+\$dbspulse_hsts\s*\{(.*?)\}", nginx_conf, re.S)
    assert mapping, "نگاشت $dbspulse_hsts پیدا نشد"
    body = mapping.group(1)
    assert re.search(r'default\s+""\s*;', body), "پیش‌فرض نگاشت باید رشتهٔ خالی باشد"
    assert "https" in body


def test_hsts_does_not_ship_with_preload(nginx_conf: str):
    """ثبت در فهرست preload مرورگرها عملاً برگشت‌ناپذیر است و نباید پیش‌فرضِ یک
    قالب عمومی باشد؛ باید تصمیم آگاهانهٔ صاحب همان دامنه باشد."""
    assert "preload" not in nginx_conf


def test_the_forwarded_for_header_is_overwritten_not_appended(nginx_conf: str):
    """رگرسیونِ فاز ۱: با $proxy_add_x_forwarded_for، آدرسی که محدودیت نرخ ورود روی
    آن کلید می‌خورد توسط خود کلاینت قابل کنترل بود — با چرخاندن یک هدر، شمارنده
    صفر می‌شد."""
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in nginx_conf
    assert "$proxy_add_x_forwarded_for" not in nginx_conf
