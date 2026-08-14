"""سنجه‌های Prometheus (P1-12).

خرابی‌های واقعی این سامانه، خرابی‌های *ساکت*اند: sweepی که دیگر اجرا نمی‌شود،
رندر PDF که چون کتابخانهٔ سیستمی نصب نیست بی‌صدا خطا می‌دهد، جهش ۴۰۱ها که نشانهٔ
حمله است، پرونده‌ای که یک ماه در یک مرحله مانده. هیچ‌کدام امروز زنگی به صدا
درنمی‌آورد؛ وقتی کشف می‌شوند که کاربر شکایت کند.

دو تصمیم:

* **مسیرها الگو ثبت می‌شوند نه مقدار.** یعنی `/api/evaluations/{evaluation_id}`
  نه `/api/evaluations/42`. اگر مقدار ثبت شود، هر شناسه یک سری زمانی جدید
  می‌سازد و بعد از چند هزار پرونده، Prometheus از کار می‌افتد (cardinality
  explosion). این متداول‌ترین اشتباه در ابزارگذاری HTTP است.
* **هیچ داده‌ای از محتوا ثبت نمی‌شود.** نه نمره، نه نام، نه شناسهٔ فرد. برچسب‌ها
  فقط متد، الگوی مسیر، کد وضعیت و نقش‌اند. سنجه‌ها معمولاً جایی می‌روند که
  کنترل دسترسی‌شان با خود برنامه یکی نیست.
"""
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

# رجیستری اختصاصی به‌جای پیش‌فرض سراسری: تست‌ها می‌توانند تمیز شروع کنند و
# سنجه‌های پیش‌فرضِ فرایند به‌طور ناخواسته منتشر نمی‌شوند.
REGISTRY = CollectorRegistry()

http_requests = Counter(
    "dbspulse_http_requests_total",
    "تعداد درخواست‌های HTTP",
    ["method", "path", "status"],
    registry=REGISTRY,
)

http_duration = Histogram(
    "dbspulse_http_request_duration_seconds",
    "مدت پاسخ‌دهی درخواست‌های HTTP",
    ["method", "path"],
    # سطل‌ها برای یک API داخلی تنظیم شده‌اند؛ پیش‌فرض کتابخانه تا ۱۰ ثانیه می‌رود
    # که برای این‌جا بی‌فایده است، ولی رندر PDF واقعاً می‌تواند چند ثانیه شود.
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

auth_failures = Counter(
    "dbspulse_auth_failures_total",
    "ورودهای ناموفق — جهش ناگهانی یعنی حملهٔ حدس رمز",
    ["reason"],
    registry=REGISTRY,
)

rate_limit_rejections = Counter(
    "dbspulse_rate_limit_rejections_total",
    "درخواست‌های ردشده به‌خاطر محدودیت نرخ",
    registry=REGISTRY,
)

workflow_transitions = Counter(
    "dbspulse_workflow_transitions_total",
    "گذارهای گردش‌کار ارزیابی به تفکیک وضعیت مقصد",
    ["to_status"],
    registry=REGISTRY,
)

pdf_renders = Counter(
    "dbspulse_pdf_renders_total",
    "رندر PDF — شکستِ پیوسته یعنی کتابخانهٔ سیستمی (WeasyPrint) نصب نیست",
    ["outcome"],
    registry=REGISTRY,
)

sweep_runs = Counter(
    "dbspulse_scheduler_sweep_runs_total",
    "اجرای کارهای زمان‌بندی‌شده",
    ["outcome"],
    registry=REGISTRY,
)

sweep_last_success_timestamp = Gauge(
    "dbspulse_scheduler_last_success_timestamp_seconds",
    "زمان آخرین اجرای موفق sweep — کهنه‌شدنش یعنی یادآوری‌ها متوقف شده‌اند",
    registry=REGISTRY,
)


db_pool_connections = Gauge(
    "dbspulse_db_pool_connections",
    "اتصال‌های استخر دیتابیس به تفکیک وضعیت (P2-05)",
    ["state"],
    registry=REGISTRY,
)

db_pool_capacity = Gauge(
    "dbspulse_db_pool_capacity",
    "سقف مطلق اتصال‌های این کارگر (pool_size + max_overflow)",
    registry=REGISTRY,
)


def refresh_pool_metrics() -> None:
    """وضعیت استخر را درست پیش از scrape می‌خواند.

    برخلاف بقیهٔ سنجه‌ها این یکی رویداد نیست، حالت است — شمردنش هنگام هر درخواست
    هم گران است و هم بی‌معنا. اشباع استخر از بیرون شبیه «دیتابیس کند شده» دیده
    می‌شود؛ این عدد همان چیزی است که این دو را از هم جدا می‌کند.
    """
    # وارداتِ داخل تابع: db.session موتور را در زمان import می‌سازد و ماژول
    # سنجه‌ها نباید این کار را به هر کسی که واردش می‌کند تحمیل کند.
    from app.db.session import pool_stats

    stats = pool_stats()
    db_pool_connections.labels(state="checked_out").set(stats["checked_out"])
    db_pool_connections.labels(state="available").set(stats["available"])
    db_pool_connections.labels(state="overflow").set(max(0, stats["overflow"]))
    db_pool_capacity.set(stats["capacity"])


def record_request(method: str, path_template: str, status_code: int, duration_seconds: float) -> None:
    http_requests.labels(method=method, path=path_template, status=str(status_code)).inc()
    http_duration.labels(method=method, path=path_template).observe(duration_seconds)
