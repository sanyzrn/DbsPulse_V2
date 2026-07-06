from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.schemas.auth import CurrentUser
from app.services.audit import log_event
from app.services.scheduled import run_all_sweeps

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/run-scheduled-jobs")
def run_scheduled_jobs(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> dict[str, int]:
    """اجرای دستی sweep های اعلان (انقضای قرارداد + تأخیر مراحل). برای ops و آزمون؛
    زمان‌بند خودکار هم همین‌ها را دوره‌ای اجرا می‌کند."""
    summary = run_all_sweeps(db)
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="scheduled_jobs_run",
        new_value=summary,
    )
    db.commit()
    return summary
