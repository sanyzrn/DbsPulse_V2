from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_capability
from app.db.session import get_db
from app.models.enums import Capability, DeliveryStatus
from app.models.notification_delivery import NotificationDelivery
from app.schemas.auth import CurrentUser
from app.schemas.notification import DeliveryQueueSummary, DeliveryRow
from app.schemas.scheduler import SchedulerRunRead
from app.services import channels
from app.services.audit import log_event
from app.services.scheduled import run_all_sweeps
from app.services.scheduler_lock import recent_runs, run_sweeps_once

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/run-scheduled-jobs")
def run_scheduled_jobs(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.view_diagnostics)),
) -> dict[str, int]:
    """اجرای دستی sweep های اعلان (انقضای قرارداد + تأخیر مراحل). برای ops و آزمون؛
    زمان‌بند خودکار هم همین‌ها را دوره‌ای اجرا می‌کند.

    از همان قفل رهبریِ زمان‌بند رد می‌شود: اگر دقیقاً همان لحظه زمان‌بند در حال اجرا
    باشد، این درخواست کار تکراری انجام نمی‌دهد و با ۴۰۹ برمی‌گردد — به‌جای ساختن
    اعلان‌های دوتایی.
    """
    run = run_sweeps_once(db, run_all_sweeps, trigger="manual")
    if run.status == "skipped_locked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="یادآوری‌های خودکار همین حالا در حال اجرا هستند؛ چند لحظه بعد دوباره تلاش کنید.",
        )

    summary = run.summary or {}
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="scheduled_jobs_run",
        new_value=summary,
    )
    db.commit()
    return summary


@router.get("/scheduler-runs", response_model=list[SchedulerRunRead])
def scheduler_runs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.view_diagnostics)),
) -> list[SchedulerRunRead]:
    """تاریخچهٔ اجرای کارهای زمان‌بندی‌شده.

    بدون این، تنها راه فهمیدن این‌که یادآوری‌ها واقعاً اجرا می‌شوند لاگ کانتینر بود —
    و اگر زمان‌بند اصلاً روشن نبود، هیچ نشانهٔ منفی‌ای وجود نداشت. سکوت از سلامت قابل
    تشخیص نبود.
    """
    return [SchedulerRunRead.model_validate(run) for run in recent_runs(db, limit)]


@router.get("/delivery-queue", response_model=DeliveryQueueSummary)
def delivery_queue(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.view_diagnostics)),
) -> DeliveryQueueSummary:
    """وضعیت صندوق خروجی اعلان‌ها (P1-03).

    بدون این صفحه، اعلانی که نرسیده هیچ ردی ندارد و «چرا فلانی خبردار نشد؟»
    بی‌جواب می‌ماند. عمداً فقط ردیف‌های مشکل‌دار نشان داده می‌شوند: در فهرستی که
    اکثرش موفق است، همان چند ردیفی که کسی باید نگاهشان کند گم می‌شوند.
    """
    counts = {
        status_value.value: db.scalar(
            select(func.count())
            .select_from(NotificationDelivery)
            .where(NotificationDelivery.status == status_value)
        )
        or 0
        for status_value in DeliveryStatus
    }
    problems = db.scalars(
        select(NotificationDelivery)
        .where(
            NotificationDelivery.status.in_([DeliveryStatus.failed, DeliveryStatus.abandoned])
        )
        .order_by(NotificationDelivery.last_attempt_at.desc())
        .limit(50)
    ).all()

    return DeliveryQueueSummary(
        channels_configured=[channel.kind.value for channel in channels.available()],
        counts=counts,
        recent_problems=[
            DeliveryRow(
                id=row.id,
                channel=row.channel.value,
                recipient=row.recipient,
                status=row.status.value,
                attempts=row.attempts,
                last_error=row.last_error,
                last_attempt_at=row.last_attempt_at,
                sent_at=row.sent_at,
                created_at=row.created_at,
            )
            for row in problems
        ],
    )
