from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.enums import UserRole
from app.models.evaluation import EvaluationRecord
from app.models.user import User
from app.schemas.audit_log import AuditLogPage, AuditLogRead
from app.schemas.auth import CurrentUser
from app.services.excel import build_audit_log_workbook

router = APIRouter(prefix="/api/audit-log", tags=["audit-log"])

# برچسب فارسی رویدادها برای خروجی Excel — هم‌راستا با AUDIT_EVENT_LABELS فرانت‌اند.
_EVENT_LABELS = {
    "status_changed": "تغییر وضعیت",
    "score_submitted": "ثبت امتیاز",
    "scores_draft_saved": "ذخیره پیش‌نویس امتیاز",
    "indicator_created": "افزودن شاخص",
    "indicator_updated": "ویرایش شاخص",
    "indicators_reordered": "تغییر ترتیب شاخص‌ها",
    "indicator_deleted": "حذف شاخص",
    "user_created": "ساخت کاربر",
    "user_updated": "ویرایش کاربر",
    "personnel_created": "افزودن پرسنل",
    "personnel_updated": "ویرایش پرسنل",
    "access_updated": "تنظیم دسترسی ارزیابی",
    "access_supervisor_cleared_on_manager_title": "حذف خودکار مسئول واحد (تغییر عنوان به مدیر)",
    "comment_added": "ثبت کامنت",
    "comment_reply_added": "ثبت پاسخ به کامنت",
    "period_created": "ایجاد دوره ارزیابی",
    "period_closed": "بستن دوره ارزیابی",
    "scheduled_jobs_run": "اجرای یادآوری‌های خودکار",
    "evaluation_returned": "برگشت پرونده",
    "evaluation_acknowledged": "رؤیت نتیجه توسط کارمند",
    "improvement_plan_created": "ایجاد برنامه بهبود",
    "improvement_plan_updated": "ویرایش برنامه بهبود",
    "improvement_plan_completed": "تکمیل برنامه بهبود",
    "improvement_plan_cancelled": "لغو برنامه بهبود",
    "excel_exported": "خروجی Excel",
    "personnel_excel_exported": "خروجی Excel پرسنل",
    "users_excel_exported": "خروجی Excel کاربران",
    "improvement_plans_excel_exported": "خروجی Excel برنامه‌های بهبود",
    "audit_log_excel_exported": "خروجی Excel گزارش رویدادها",
    "pdf_downloaded": "دریافت PDF",
    "login_succeeded": "ورود موفق",
    "login_failed": "ورود ناموفق",
    "password_changed_self": "تغییر رمز توسط خود کاربر",
}


def _build_filters(
    event_type: str | None,
    evaluation_record_id: int | None,
    created_from: date | None,
    created_to: date | None,
) -> list:
    filters = []
    if event_type is not None:
        filters.append(AuditLog.event_type == event_type)
    if evaluation_record_id is not None:
        filters.append(AuditLog.evaluation_record_id == evaluation_record_id)
    if created_from is not None:
        filters.append(AuditLog.created_at >= created_from)
    if created_to is not None:
        # بازه شامل خودِ روز پایان است
        filters.append(AuditLog.created_at < created_to + timedelta(days=1))
    return filters


def _query_rows(db: Session, filters: list, *, limit: int | None, offset: int):
    query = (
        select(AuditLog, User.username, EvaluationRecord.evaluation_code)
        .join(User, User.id == AuditLog.actor_user_id, isouter=True)
        .join(EvaluationRecord, EvaluationRecord.id == AuditLog.evaluation_record_id, isouter=True)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
    )
    if limit is not None:
        query = query.limit(limit)
    return db.execute(query).all()


@router.get("", response_model=AuditLogPage)
def list_audit_log(
    event_type: str | None = None,
    evaluation_record_id: int | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> AuditLogPage:
    filters = _build_filters(event_type, evaluation_record_id, created_from, created_to)
    total = db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    # نام کاربر و کد ارزیابی با JOIN در همان کوئری صفحه حل می‌شوند؛ نسخه قبلی کل
    # جدول users و evaluation_records را برای ۵۰ ردیف در حافظه بارگذاری می‌کرد.
    rows = _query_rows(db, filters, limit=limit, offset=offset)
    items = [
        AuditLogRead(
            id=row.id,
            evaluation_record_id=row.evaluation_record_id,
            evaluation_code=evaluation_code,
            actor_user_id=row.actor_user_id,
            actor_username=username,
            event_type=row.event_type,
            old_value=row.old_value,
            new_value=row.new_value,
            created_at=row.created_at,
        )
        for row, username, evaluation_code in rows
    ]
    return AuditLogPage(total=total, items=items)


@router.get("/export.xlsx")
def export_audit_log_excel(
    event_type: str | None = None,
    evaluation_record_id: int | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> Response:
    """خروجی Excel از گزارش رویدادها (فقط HR) با همان فیلترهای فهرست. برای پرهیز از
    فایل‌های عظیم، حداکثر ۵۰۰۰ ردیف اخیرِ منطبق با فیلتر صادر می‌شود."""
    filters = _build_filters(event_type, evaluation_record_id, created_from, created_to)
    rows = _query_rows(db, filters, limit=5000, offset=0)
    entries = [(row, username, evaluation_code) for row, username, evaluation_code in rows]
    return Response(
        content=build_audit_log_workbook(entries, _EVENT_LABELS),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="audit-log.xlsx"'},
    )
