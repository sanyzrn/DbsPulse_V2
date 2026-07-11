import logging
import time
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
from app.core.rate_limit import limiter
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
    return JSONResponse(
        status_code=429,
        content={"detail": "تعداد تلاش‌های شما بیش از حد مجاز است؛ کمی بعد دوباره امتحان کنید."},
        headers={"Retry-After": "60"},
    )


@app.middleware("http")
async def request_context(request: Request, call_next):
    """شناسه یکتا برای هر درخواست + لاگ ساخت‌یافته + پاسخ ۵۰۰ امن به‌جای traceback خام."""
    request_id = uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_id=%s %s %s -> unhandled error", request_id, request.method, request.url.path
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "خطای داخلی سرور رخ داد؛ در صورت تکرار، این شناسه را به پشتیبانی اعلام کنید: "
                + request_id
            },
            headers={"X-Request-ID": request_id},
        )
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_id=%s %s %s -> %s (%.0fms)",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
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
def ready(db: Session = Depends(get_db)) -> dict:
    """readiness — اتصال دیتابیس هم بررسی می‌شود"""
    db.execute(text("SELECT 1"))
    return {"status": "ready"}
