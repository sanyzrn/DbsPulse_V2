"""کارهای زمان‌بندی‌شده (sweep) که سامانه را از حالت pull-based خارج می‌کنند:

۱) هشدار انقضای قرارداد به منابع انسانی برای کسانی که ارزیابیِ باز ندارند.
۲) یادآوری تأخیر (SLA) به صاحبِ فعلی پرونده‌هایی که مدت‌هاست در جریان مانده‌اند.

توابع خالص‌اند (فقط db می‌گیرند و اعلان می‌سازند)؛ commit با فراخواننده است تا هم از
endpoint دستی و هم از زمان‌بند و هم در تست قابل استفاده باشند. با notify_once از اسپم
جلوگیری می‌شود.
"""
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import (
    EvaluationStatus,
    ImprovementPlanStatus,
    PersonnelStatus,
    UserRole,
)
from app.models.evaluation import EvaluationRecord
from app.models.improvement_plan import ImprovementPlan
from app.models.personnel import Personnel
from app.models.user import User
from app.services.login_guard import purge_stale
from app.services.notifications import notify_once
from app.services.workflow import IS_OPEN_RECORD


def _active_hr_ids(db: Session) -> list[int]:
    return list(
        db.scalars(select(User.id).where(User.role == UserRole.hr, User.is_active.is_(True)))
    )


def run_contract_expiry_sweep(db: Session) -> int:
    """به HR برای هر پرسنل فعالِ رو به انقضا که ارزیابی بازی ندارد، یک‌بار (در پنجره
    dedup) هشدار می‌دهد. خروجی: تعداد اعلان ساخته‌شده."""
    horizon = date.today() + timedelta(days=settings.contract_expiry_alert_days)

    open_evaluation_exists = (
        select(EvaluationRecord.id)
        .where(
            EvaluationRecord.subject_personnel_id == Personnel.id,
            IS_OPEN_RECORD,
        )
        .exists()
    )
    expiring = db.execute(
        select(Personnel.id, Personnel.full_name, Personnel.contract_end_date)
        .where(
            Personnel.status == PersonnelStatus.active,
            Personnel.contract_end_date <= horizon,
            ~open_evaluation_exists,
        )
        .order_by(Personnel.contract_end_date)
    ).all()

    hr_ids = _active_hr_ids(db)
    created = 0
    today = date.today()
    for personnel_id, full_name, end_date in expiring:
        days = (end_date - today).days
        when = f"{days} روز دیگر" if days >= 0 else f"{abs(days)} روز پیش (منقضی‌شده)"
        message = (
            f"قرارداد «{full_name}» {when} به پایان می‌رسد و هنوز ارزیابی‌ای برایش آغاز نشده است"
        )
        for hr_id in hr_ids:
            if notify_once(
                db,
                user_id=hr_id,
                type_="contract_expiry",
                message=message,
                dedup_key=f"contract_expiry:{personnel_id}",
                within_days=settings.notification_dedup_days,
                link="/hr/dashboard",
            ):
                created += 1
    return created


def _current_owner_ids(db: Session, record: EvaluationRecord) -> list[int]:
    is_manager_path = record.unit_supervisor_user_id is None
    if record.status == EvaluationStatus.draft:
        owner = record.deputy_user_id if is_manager_path else record.unit_supervisor_user_id
        return [owner] if owner is not None else []
    if record.status == EvaluationStatus.submitted:
        return _active_hr_ids(db)
    if record.status == EvaluationStatus.hr_approved:
        return [record.deputy_user_id]
    if record.status == EvaluationStatus.deputy_approved:
        return [record.ceo_user_id]
    return []


def run_sla_sweep(db: Session) -> int:
    """به صاحبِ فعلیِ هر پرونده‌ای که بیش از حد آستانه *در همین مرحله* مانده، یادآوری
    می‌فرستد. dedup_key شامل وضعیت است تا با هر مرحله جدیدِ گیرکرده دوباره فعال شود."""
    # قبلاً معیار created_at بود، یعنی «سن کل پرونده». نتیجه‌اش دو خطای متقارن بود:
    # پرونده‌ای که سه هفته در مراحل قبلی چرخیده، همان لحظهٔ رسیدن به مرحلهٔ جدید
    # فوراً تأخیردار اعلام می‌شد (مسئول تازه‌کار بی‌دلیل نهیب می‌خورد)، و هیچ راهی
    # نبود بفهمیم واقعاً کدام مرحله کند است.
    cutoff = datetime.now(UTC) - timedelta(days=settings.sla_reminder_days)
    stalled = db.scalars(
        select(EvaluationRecord).where(
            IS_OPEN_RECORD,
            EvaluationRecord.stage_entered_at <= cutoff,
        )
    )

    created = 0
    for record in stalled:
        message = (
            f"پرونده {record.evaluation_code} ({record.subject.full_name}) بیش از "
            f"{settings.sla_reminder_days} روز است در همین مرحله منتظر اقدام شماست"
        )
        for owner_id in _current_owner_ids(db, record):
            if notify_once(
                db,
                user_id=owner_id,
                type_="sla_reminder",
                message=message,
                dedup_key=f"sla:{record.id}:{record.status.value}",
                within_days=settings.sla_reminder_days,
                evaluation_record_id=record.id,
                link=f"/evaluations/{record.id}",
            ):
                created += 1
    return created


def run_orphaned_case_sweep(db: Session) -> int:
    """پرونده‌های بازی که مسئولِ مرحلهٔ فعلی‌شان دیگر کاربر فعالی نیست را به HR گزارش می‌کند.

    این دقیقاً همان حالتی است که ابزارهای لغو/بازتخصیص برای آن ساخته شدند: گذار،
    برابری `current_user.id` با مسئول ثبت‌شده را لازم دارد، پس اگر آن حساب غیرفعال
    شود پرونده تا ابد سر جایش می‌ماند. بدون این جارو، HR فقط موقع تمدید قرارداد —
    یعنی بدترین لحظهٔ ممکن — متوجهش می‌شد.
    """
    open_records = db.scalars(select(EvaluationRecord).where(IS_OPEN_RECORD))
    hr_ids = _active_hr_ids(db)
    created = 0

    for record in open_records:
        owner_ids = _current_owner_ids(db, record)
        # وضعیت submitted صاحب مشخصی ندارد (هر HR فعالی می‌تواند اقدام کند)، پس
        # «بی‌صاحب» بودنش معنای دیگری دارد و این‌جا موضوعیت ندارد.
        if not owner_ids or record.status == EvaluationStatus.submitted:
            continue

        active_owners = db.scalars(
            select(User.id).where(User.id.in_(owner_ids), User.is_active.is_(True))
        ).all()
        if active_owners:
            continue

        message = (
            f"پرونده {record.evaluation_code} ({record.subject.full_name}) گیر کرده است: "
            "مسئول مرحلهٔ فعلی دیگر کاربر فعالی نیست. مسئول جدید تعیین کنید یا پرونده را لغو کنید."
        )
        for hr_id in hr_ids:
            if notify_once(
                db,
                user_id=hr_id,
                type_="orphaned_case",
                message=message,
                dedup_key=f"orphaned:{record.id}:{record.status.value}",
                within_days=settings.notification_dedup_days,
                evaluation_record_id=record.id,
                link=f"/evaluations/{record.id}",
            ):
                created += 1
    return created


def run_improvement_review_sweep(db: Session) -> int:
    """برای برنامه‌های بهبودِ بازی که تاریخ بازنگری‌شان نزدیک (یا گذشته) است، به HR و
    مسئول پیگیری یادآوری می‌فرستد. dedup_key شامل تاریخ بازنگری است تا با جابه‌جایی
    تاریخ دوباره فعال شود."""
    horizon = date.today() + timedelta(days=settings.improvement_review_alert_days)
    due_plans = db.scalars(
        select(ImprovementPlan).where(
            ImprovementPlan.status == ImprovementPlanStatus.open,
            ImprovementPlan.review_date <= horizon,
        )
    )

    hr_ids = _active_hr_ids(db)
    created = 0
    today = date.today()
    for plan in due_plans:
        days = (plan.review_date - today).days
        when = f"{days} روز دیگر" if days >= 0 else f"{abs(days)} روز پیش (گذشته)"
        message = (
            f"تاریخ بازنگری برنامه بهبود «{plan.title}» "
            f"({plan.personnel.full_name}) {when} است"
        )
        recipients = set(hr_ids)
        if plan.owner_user_id is not None:
            recipients.add(plan.owner_user_id)
        for user_id in recipients:
            if notify_once(
                db,
                user_id=user_id,
                type_="improvement_review_due",
                message=message,
                dedup_key=f"improvement_review:{plan.id}:{plan.review_date.isoformat()}",
                within_days=settings.notification_dedup_days,
                link=f"/improvement-plans/{plan.id}",
            ):
                created += 1
    return created


def run_all_sweeps(db: Session) -> dict[str, int]:
    """همه sweep ها را اجرا و commit می‌کند؛ نقطه ورود زمان‌بند و endpoint دستی."""
    summary = {
        "contract_expiry": run_contract_expiry_sweep(db),
        "sla_reminder": run_sla_sweep(db),
        "orphaned_case": run_orphaned_case_sweep(db),
        "improvement_review": run_improvement_review_sweep(db),
        # نگهداری، نه اعلان: ردیف‌های منقضیِ شمارش تلاش ورود را پاک می‌کند تا جدول
        # با نام‌های کاربریِ تصادفیِ یک حملهٔ enumeration باد نکند.
        "stale_login_attempts_purged": purge_stale(db),
    }
    db.commit()
    return summary
