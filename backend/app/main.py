import logging
import secrets
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routers import (
    admin,
    audit_log,
    auth,
    config,
    dashboard,
    evaluation_access,
    evaluations,
    improvement_plans,
    indicators,
    me,
    notifications,
    periods,
    personnel,
    reports,
    users,
    verify,
)
from app.core.config import settings
from app.core.metrics import (
    REGISTRY,
    rate_limit_rejections,
    record_request,
    sweep_last_success_timestamp,
)
from app.core.rate_limit import limiter
from app.core.readiness import last_successful_sweep, migration_state
from app.core.scheduler import lifespan
from app.db.session import get_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("dbspulse")

# در production مستندات Swagger/OpenAPI عمداً خاموش است تا نقشه کامل API در
# دسترس عموم نباشد؛ برای توسعه محلی همچنان روی /docs فعال است.
_docs_disabled = settings.environment == "production"

app = FastAPI(
    title="DbsPulse — سامانه ارزیابی عملکرد",
    docs_url=None if _docs_disabled else "/docs",
    redoc_url=None if _docs_disabled else "/redoc",
    openapi_url=None if _docs_disabled else "/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    rate_limit_rejections.inc()
    return JSONResponse(
        status_code=429,
        content={"detail": "تعداد تلاش‌های شما بیش از حد مجاز است؛ کمی بعد دوباره امتحان کنید."},
        headers={"Retry-After": "60"},
    )


def _path_template(request: Request) -> str:
    """الگوی مسیر، نه مقدارش.

    `/api/evaluations/{evaluation_id}` ثبت می‌شود نه `/api/evaluations/42`. اگر
    مقدار ثبت شود هر شناسه یک سری زمانی تازه می‌سازد و Prometheus بعد از چند
    هزار پرونده از پا درمی‌آید. مسیرهای ناشناخته هم زیر یک برچسب ثابت می‌روند تا
    اسکن ۴۰۴ نتواند کاردینالیتی را منفجر کند.
    """
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path or "<unmatched>"


@app.middleware("http")
async def request_context(request: Request, call_next):
    """شناسه یکتا برای هر درخواست + لاگ ساخت‌یافته + سنجه + پاسخ ۵۰۰ امن."""
    request_id = uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_id=%s %s %s -> unhandled error", request_id, request.method, request.url.path
        )
        record_request(request.method, _path_template(request), 500, time.perf_counter() - start)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "خطای داخلی سرور رخ داد؛ در صورت تکرار، این شناسه را به پشتیبانی اعلام کنید: "
                + request_id
            },
            headers={"X-Request-ID": request_id},
        )
    duration = time.perf_counter() - start
    record_request(request.method, _path_template(request), response.status_code, duration)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_id=%s %s %s -> %s (%.0fms)",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration * 1000,
    )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(config.router)
app.include_router(personnel.router)
app.include_router(evaluation_access.router)
app.include_router(users.router)
app.include_router(indicators.router)
app.include_router(evaluations.router)
app.include_router(improvement_plans.router)
app.include_router(me.router)
app.include_router(dashboard.router)
app.include_router(reports.router)
app.include_router(audit_log.router)
app.include_router(notifications.router)
app.include_router(periods.router)
app.include_router(verify.router)


@app.get("/api/health")
def health() -> dict:
    """liveness — فقط بالا بودن پروسه"""
    return {"status": "ok"}


@app.get("/api/health/ready")
def ready(response: Response, db: Session = Depends(get_db)) -> dict:
    """readiness — اتصال دیتابیس، هم‌خوانی نسخهٔ مایگریشن، و تازگی آخرین sweep.

    «هم‌خوانی مایگریشن» مهم‌ترین بخش است: کانتینری که بالا آمده ولی مایگریشن‌ها
    اجرا نشده‌اند، از بیرون سالم به‌نظر می‌رسد و بعد روی اولین درخواستِ جدی خطا
    می‌دهد. این حالت واقعاً «آماده» نیست، پس ۵۰۳ می‌گیرد.

    کهنه‌بودن sweep عمداً readiness را نمی‌شکند: برنامه همچنان درست سرویس می‌دهد
    و بیرون‌کشیدنش از load balancer اوضاع را بدتر می‌کند. گزارش می‌شود تا
    هشداردهنده تصمیم بگیرد.
    """
    checks: dict[str, object] = {}
    healthy = True

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001 — پاسخ readiness نباید جزئیات داخلی بدهد
        logger.exception("readiness: database check failed")
        checks["database"] = "unreachable"
        healthy = False

    expected, applied = migration_state(db)
    checks["migration_head"] = {"expected": expected, "applied": applied}
    if expected is not None and applied != expected:
        healthy = False

    last_success = last_successful_sweep(db)
    checks["last_successful_sweep"] = last_success.isoformat() if last_success else None
    if last_success is not None:
        sweep_last_success_timestamp.set(last_success.timestamp())

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if healthy else "not-ready", "checks": checks}


@app.get("/metrics", include_in_schema=False)
def metrics(request: Request) -> Response:
    """سنجه‌ها در قالب Prometheus.

    پشت توکن است و اگر توکنی تنظیم نشده باشد اصلاً وجود ندارد (۴۰۴). سنجه‌ها
    نام مسیرها، حجم ترافیک و نرخ خطا را لو می‌دهند؛ این‌ها برای کسی که دنبال
    نقطهٔ ضعف می‌گردد اطلاعات مفیدی است، پس پیش‌فرضِ «باز» غلط بود.
    """
    token = settings.metrics_token
    if not token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    provided = request.headers.get("authorization", "")
    expected = f"Bearer {token}"
    # مقایسهٔ ثابت‌زمان: مقایسهٔ معمولی رشته، طول پیشوند مشترک را از روی زمان لو می‌دهد
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
