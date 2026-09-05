"""ساخت اعلان درون‌برنامه‌ای برای گیرنده(های) هر رویداد گردش‌کار.

اعلان‌ها در همان تراکنشِ رویداد ساخته می‌شوند (بدون commit جدا) تا با خود گذار
atomic باشند؛ اگر گذار rollback شود اعلانی هم باقی نمی‌ماند.
"""
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.evaluation import EvaluationRecord
from app.models.notification import Notification


def _queue_outbound(db: Session, notification: Notification) -> None:
    """ردیف صندوق خروجی را در همان تراکنش می‌سازد (P1-03).

    وارداتِ داخل تابع عمدی است: delivery به کانال‌ها و کانال‌ها به تنظیمات وابسته‌اند،
    و این ماژول در همه‌جای گردش‌کار وارد می‌شود. نگه‌داشتن آن زنجیره بیرون از
    زمانِ import، وابستگی چرخه‌ای را از ابتدا ناممکن می‌کند.

    فقط *ثبت* می‌شود؛ هیچ ارسالی این‌جا رخ نمی‌دهد. اگر ارسال روی مسیر درخواست
    بود، کندی سرویس پیامک به شکست «تأیید پرونده» ترجمه می‌شد.
    """
    from app.services.delivery import enqueue_for

    # شناسه لازم است تا ردیف تحویل به آن ارجاع دهد
    db.flush()
    enqueue_for(db, notification)


def notify(
    db: Session,
    user_ids: Iterable[int],
    type_: str,
    message: str,
    evaluation_record_id: int | None = None,
    link: str | None = None,
) -> None:
    for user_id in set(user_ids):
        notification = Notification(
            user_id=user_id,
            type=type_,
            message=message,
            link=link,
            evaluation_record_id=evaluation_record_id,
        )
        db.add(notification)
        _queue_outbound(db, notification)


def notify_once(
    db: Session,
    user_id: int,
    type_: str,
    message: str,
    dedup_key: str,
    within_days: int,
    evaluation_record_id: int | None = None,
    link: str | None = None,
) -> bool:
    """اگر همین کاربر در پنجره اخیر اعلانی با همین dedup_key گرفته باشد، دوباره نمی‌سازد.
    خروجی True یعنی اعلان جدید ساخته شد. برای sweep های تکرارشونده تا از اسپم جلوگیری شود."""
    cutoff = datetime.now(UTC) - timedelta(days=within_days)
    exists = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.dedup_key == dedup_key,
            Notification.created_at >= cutoff,
        )
    )
    if exists:
        return False
    notification = Notification(
        user_id=user_id,
        type=type_,
        message=message,
        link=link,
        evaluation_record_id=evaluation_record_id,
        dedup_key=dedup_key,
    )
    db.add(notification)
    _queue_outbound(db, notification)
    return True


def _active_user_ids_with_role(db: Session, role: UserRole) -> list[int]:
    from app.models.user import User

    return list(db.scalars(select(User.id).where(User.role == role, User.is_active.is_(True))))


def notify_for_workflow_action(db: Session, record: EvaluationRecord, action: str) -> None:
    """نفر بعدی زنجیره (یا نفر قبلی، در برگشت پرونده) را از رویداد باخبر می‌کند."""
    code = record.evaluation_code
    name = record.subject.full_name
    link = f"/evaluations/{record.id}"

    evaluator_id = (
        record.ceo_user_id
        if record.unit_supervisor_user_id is None and record.deputy_user_id is None
        else record.deputy_user_id
        if record.unit_supervisor_user_id is None
        else record.unit_supervisor_user_id
    )
    # زنجیره می‌تواند معاونت نداشته باشد؛ آن‌وقت نفرِ بعد از منابع انسانی خودِ
    # مدیرعامل است. بدون این، اعلان به `None` فرستاده می‌شد و کل گذارِ تأیید
    # منابع انسانی با NotNullViolation شکست می‌خورد — یعنی نبودِ معاونت، پرونده
    # را در همان مرحله قفل می‌کرد.
    after_hr_id = record.deputy_user_id or record.ceo_user_id

    recipients: list[int] = []
    message = ""
    if action in ("submit", "manager_submit", "direct_ceo_submit"):
        recipients = _active_user_ids_with_role(db, UserRole.hr)
        message = f"پرونده {code} ({name}) در صف بررسی منابع انسانی قرار گرفت"
    elif action == "hr_approve":
        recipients = [after_hr_id]
        message = f"پرونده {code} ({name}) در انتظار بررسی و تأیید شماست"
    elif action == "hr_approve_manager":
        # مسیر «مدیر»: مرحلهٔ معاونت مصرف شده، پس نفرِ بعدی مدیرعامل است.
        recipients = [record.ceo_user_id]
        message = f"پرونده {code} ({name}) در انتظار تأیید نهایی شماست"
    elif action == "hr_finalize_direct_ceo":
        recipients = [record.ceo_user_id]
        message = f"پرونده {code} ({name}) توسط منابع انسانی نهایی شد"
    elif action == "deputy_approve":
        recipients = [record.ceo_user_id]
        message = f"پرونده {code} ({name}) در انتظار تأیید نهایی شماست"
    elif action == "ceo_finalize":
        recipients = [evaluator_id] if evaluator_id is not None else []
        message = f"پرونده {code} ({name}) تأیید نهایی شد"
    elif action == "hr_return":
        # `evaluator_id` نه `unit_supervisor_user_id`: در مسیر «مدیر» دومی خالی
        # است، پس برگشتِ منابع انسانی به هیچ‌کس اعلان نمی‌داد و معاونت هیچ‌وقت
        # نمی‌فهمید پرونده‌اش برگشته — پرونده در `draft` می‌ماند و کسی خبر ندارد.
        recipients = [evaluator_id] if evaluator_id is not None else []
        message = f"پرونده {code} ({name}) توسط منابع انسانی برگشت داده شد؛ دلیل در کامنت‌های پرونده"
    elif action == "deputy_return":
        recipients = _active_user_ids_with_role(db, UserRole.hr)
        message = f"پرونده {code} ({name}) توسط معاونت برگشت داده شد؛ دلیل در کامنت‌های پرونده"
    elif action == "ceo_return":
        # برگشت از مدیرعامل هم به همان کسی می‌رود که پرونده را به او داده بود.
        recipients = [after_hr_id]
        message = f"پرونده {code} ({name}) توسط مدیرعامل برگشت داده شد؛ دلیل در کامنت‌های پرونده"
    elif action == "ceo_return_manager":
        # در مسیر «مدیر» پرونده به صف منابع انسانی برمی‌گردد، نه به معاونت.
        recipients = _active_user_ids_with_role(db, UserRole.hr)
        message = f"پرونده {code} ({name}) توسط مدیرعامل برگشت داده شد؛ دلیل در کامنت‌های پرونده"
    elif action == "cancel":
        # همهٔ کسانی که روی این پرونده نقشی داشتند باید بدانند دیگر منتظرشان نیست.
        recipients = [
            user_id
            for user_id in (record.unit_supervisor_user_id, record.deputy_user_id, record.ceo_user_id)
            if user_id is not None
        ]
        message = f"پرونده {code} ({name}) توسط منابع انسانی لغو شد؛ دلیل در کامنت‌های پرونده"

    if recipients and message:
        notify(
            db,
            recipients,
            type_=f"workflow_{action}",
            message=message,
            evaluation_record_id=record.id,
            link=link,
        )

    if action in ("ceo_finalize", "hr_finalize_direct_ceo"):
        # اگر خود کارمند حساب فعال دارد، نتیجه نهایی به او هم ابلاغ می‌شود («کارنامه من»)
        from app.models.user import User

        employee_ids = list(
            db.scalars(
                select(User.id).where(
                    User.role == UserRole.employee,
                    User.personnel_id == record.subject_personnel_id,
                    User.is_active.is_(True),
                )
            )
        )
        if employee_ids:
            notify(
                db,
                employee_ids,
                type_="evaluation_finalized_self",
                message=f"ارزیابی عملکرد شما ({code}) نهایی شد؛ نتیجه در «کارنامه من» قابل مشاهده است",
                evaluation_record_id=record.id,
                link="/me",
            )


def notify_stage_owner_reassigned(
    db: Session, record: EvaluationRecord, new_owner_id: int, stage_label: str
) -> None:
    """مسئول جدید مرحله باید بداند پرونده‌ای روی میزش آمده — وگرنه پرونده دوباره
    همان‌جا می‌ماند و بازتخصیص هیچ چیزی را حل نکرده است."""
    notify(
        db,
        [new_owner_id],
        type_="workflow_reassigned",
        message=(
            f"پرونده {record.evaluation_code} ({record.subject.full_name}) به‌عنوان "
            f"«{stage_label}» به شما واگذار شد"
        ),
        evaluation_record_id=record.id,
        link=f"/evaluations/{record.id}",
    )
