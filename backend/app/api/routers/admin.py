from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.schemas.auth import CurrentUser
from app.schemas.scheduler import SchedulerRunRead
from app.services.audit import log_event
from app.services.scheduled import run_all_sweeps
from app.services.scheduler_lock import recent_runs, run_sweeps_once

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/run-scheduled-jobs")
def run_scheduled_jobs(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
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
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> list[SchedulerRunRead]:
    """تاریخچهٔ اجرای کارهای زمان‌بندی‌شده.

    بدون این، تنها راه فهمیدن این‌که یادآوری‌ها واقعاً اجرا می‌شوند لاگ کانتینر بود —
    و اگر زمان‌بند اصلاً روشن نبود، هیچ نشانهٔ منفی‌ای وجود نداشت. سکوت از سلامت قابل
    تشخیص نبود.
    """
    return [SchedulerRunRead.model_validate(run) for run in recent_runs(db, limit)]
