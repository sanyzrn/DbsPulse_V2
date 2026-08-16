"""ساخت دسته‌ای ارزیابی برای یک کوهورت (P2-03).

باز کردن یک چرخهٔ سالانه برای دویست نفر، امروز یعنی دویست‌بار ساختِ دستی — و هر
کدام می‌تواند به دلیل خودش شکست بخورد (پرسنل غیرفعال، نبودِ ردیف دسترسی، پروندهٔ
بازِ موجود) بدون اینکه کسی گزارش یک‌جای «چه چیزی موفق شد و چه چیزی نه» داشته
باشد. این دقیقاً لحظه‌ای است که منابع انسانی بیشترین نیاز را به ابزار دارد و
بیشترین احتمال را که رهایش کند و برود سراغ Excel.

سه تصمیم که شکل این ماژول را ساخته‌اند:

**۱. پیش‌بررسی و اجرا از یک تابع می‌آیند.** اگر «پیش‌نمایش» کد جدایی داشته باشد،
دیر یا زود چیزی را وعده می‌دهد که اجرا انجام نمی‌دهد — و بدترین شکل این خطا آن
است که کاربر بر اساس پیش‌نمایش تصمیم بگیرد. این‌جا `plan()` همان تحلیل را
می‌سازد و `execute()` روی همان نتیجه عمل می‌کند.

**۲. هر رکورد savepoint خودش را دارد.** یک شکست وسط کار نباید صد رکوردِ ساخته‌شدهٔ
قبلی را برگرداند. HR باید بتواند مشکل چند نفر را حل کند و دوباره اجرا کند، نه
اینکه از صفر شروع کند.

**۳. گاردِ «یک پروندهٔ باز» دور زده نمی‌شود.** وسوسه‌اش هست — چون در حالت دسته‌ای
«رد شد» شبیه خطا به‌نظر می‌رسد — ولی همان گارد است که جلوی دو پروندهٔ هم‌زمان
برای یک نفر را می‌گیرد. رد شدن این‌جا نتیجهٔ درست است، نه استثنا.
"""
from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import EvaluationStatus, PeriodStatus, PersonnelStatus
from app.models.evaluation import EvaluationRecord
from app.models.evaluation_access import EvaluationAccess
from app.models.evaluation_period import EvaluationPeriod
from app.models.personnel import Personnel
from app.services.evaluation import next_evaluation_code
from app.services.indicator_framework import ensure_framework
from app.services.scoring_scheme import active_scheme
from app.services.workflow import IS_OPEN_RECORD


class BulkOutcome(str, Enum):
    """چه اتفاقی برای این فرد افتاد (یا می‌افتاد).

    سه دستهٔ متمایز، عمداً جدا از هم:

    * `created` — ساخته شد.
    * `skipped_*` — کاری لازم نبود. این خطا نیست و نباید مثل خطا دیده شود.
    * `blocked_*` — کاری لازم بود ولی نشد، و *کسی باید کاری بکند*. این‌ها همان
      ردیف‌هایی‌اند که باید در UI بالا بیایند.
    """

    created = "created"
    skipped_already_open = "skipped_already_open"
    blocked_inactive = "blocked_inactive"
    blocked_no_access_row = "blocked_no_access_row"
    blocked_no_supervisor = "blocked_no_supervisor"
    blocked_conflict = "blocked_conflict"


#: توضیح فارسیِ هر نتیجه — یک‌جا، تا پیام‌ها بین پیش‌نمایش و اجرا یکی بمانند.
OUTCOME_LABELS: dict[BulkOutcome, str] = {
    BulkOutcome.created: "ارزیابی ساخته می‌شود",
    BulkOutcome.skipped_already_open: "از قبل یک پروندهٔ باز دارد",
    BulkOutcome.blocked_inactive: "پرسنل غیرفعال است",
    BulkOutcome.blocked_no_access_row: "دسترسی زنجیرهٔ ارزیابی برایش تعریف نشده است",
    BulkOutcome.blocked_no_supervisor: "مسئول واحد برایش تعیین نشده است",
    BulkOutcome.blocked_conflict: "هم‌زمان پروندهٔ دیگری برایش ساخته شد",
}

BLOCKED = {
    BulkOutcome.blocked_inactive,
    BulkOutcome.blocked_no_access_row,
    BulkOutcome.blocked_no_supervisor,
    BulkOutcome.blocked_conflict,
}


@dataclass(frozen=True)
class CohortFilter:
    """تعریف کوهورت. همهٔ فیلترها ترکیب‌پذیرند و خالی یعنی «همه»."""

    org_unit: str | None = None
    only_managers: bool | None = None
    contract_ends_before: date | None = None

    def conditions(self) -> list:
        # پرسنل غیرفعال عمداً از فیلتر بیرون *نمی‌رود*: اگر بی‌صدا حذف شود، HR
        # هرگز نمی‌فهمد چرا فلانی در فهرست نیست. به‌جایش با نتیجهٔ blocked_inactive
        # می‌آید و دلیلش را می‌گوید.
        conditions = []
        if self.org_unit:
            conditions.append(Personnel.org_unit == self.org_unit)
        if self.only_managers is not None:
            conditions.append(Personnel.is_manager.is_(self.only_managers))
        if self.contract_ends_before is not None:
            conditions.append(Personnel.contract_end_date <= self.contract_ends_before)
        return conditions


@dataclass
class PersonPlan:
    """آنچه برای یک نفر خواهد شد (یا شد)."""

    personnel_id: int
    full_name: str
    org_unit: str
    outcome: BulkOutcome
    #: شناسهٔ پروندهٔ مرتبط — پروندهٔ بازِ موجود، یا پروندهٔ تازه‌ساخته‌شده
    evaluation_id: int | None = None
    evaluation_code: str | None = None
    #: مسئولی که پرونده به او سپرده می‌شود (نمره‌دهندهٔ اول)
    assignee_user_id: int | None = None
    #: مسیر «مدیر» — معاونت خودش نمره‌دهندهٔ اول است و پرونده مستقیماً در وضعیت
    #: hr_approved ساخته می‌شود. در پاسخ API نمی‌آید؛ فقط execute به آن نیاز دارد.
    manager_path: bool = False

    @property
    def reason(self) -> str:
        return OUTCOME_LABELS[self.outcome]


def _load_cohort(db: Session, cohort: CohortFilter) -> list[Personnel]:
    return list(
        db.scalars(
            select(Personnel).where(*cohort.conditions()).order_by(Personnel.full_name)
        )
    )


def plan(db: Session, cohort: CohortFilter) -> list[PersonPlan]:
    """اجرای خشک: هیچ چیزی نوشته نمی‌شود.

    دقیقاً همان تصمیم‌هایی گرفته می‌شود که `execute` می‌گیرد، پس پیش‌نمایش وعدهٔ
    چیزی را نمی‌دهد که اجرا انجام ندهد.
    """
    people = _load_cohort(db, cohort)
    if not people:
        return []

    person_ids = [p.id for p in people]
    access_by_person = {
        row.personnel_id: row
        for row in db.scalars(
            select(EvaluationAccess).where(EvaluationAccess.personnel_id.in_(person_ids))
        )
    }
    open_by_person = {
        record.subject_personnel_id: record
        for record in db.scalars(
            select(EvaluationRecord).where(
                EvaluationRecord.subject_personnel_id.in_(person_ids), IS_OPEN_RECORD
            )
        )
    }

    plans = []
    for person in people:
        plans.append(_plan_one(person, access_by_person.get(person.id), open_by_person.get(person.id)))
    return plans


def _plan_one(
    person: Personnel,
    access: EvaluationAccess | None,
    open_record: EvaluationRecord | None,
) -> PersonPlan:
    base = {
        "personnel_id": person.id,
        "full_name": person.full_name,
        "org_unit": person.org_unit,
    }
    # ترتیب بررسی‌ها معنا دارد: «پروندهٔ باز دارد» پیش از «غیرفعال است» می‌آید،
    # چون پروندهٔ بازِ یک پرسنلِ تازه‌غیرفعال‌شده واقعیتِ مهم‌تری است — HR باید
    # ببیند پرونده‌ای هست که تکلیفش روشن نیست.
    if open_record is not None:
        return PersonPlan(
            **base,
            outcome=BulkOutcome.skipped_already_open,
            evaluation_id=open_record.id,
            evaluation_code=open_record.evaluation_code,
        )
    if person.status != PersonnelStatus.active:
        return PersonPlan(**base, outcome=BulkOutcome.blocked_inactive)
    if access is None:
        return PersonPlan(**base, outcome=BulkOutcome.blocked_no_access_row)
    if not person.is_manager and access.unit_supervisor_user_id is None:
        return PersonPlan(**base, outcome=BulkOutcome.blocked_no_supervisor)

    # مسیر «مدیر»: معاونت خودش نمره‌دهندهٔ اول است و پرونده مستقیماً در وضعیت
    # hr_approved ساخته می‌شود — همان قاعده‌ای که create_evaluation دارد.
    assignee = access.deputy_user_id if person.is_manager else access.unit_supervisor_user_id
    return PersonPlan(
        **base,
        outcome=BulkOutcome.created,
        assignee_user_id=assignee,
        manager_path=person.is_manager,
    )


def execute(db: Session, cohort: CohortFilter) -> list[PersonPlan]:
    """اجرای واقعی. برای هر رکورد یک savepoint، تا شکستِ یکی بقیه را برنگرداند.

    commit با فراخواننده است — مثل بقیهٔ سرویس‌ها — تا لاگ ممیزی در همان تراکنش
    بنشیند.
    """
    plans = plan(db, cohort)
    open_period = db.scalar(
        select(EvaluationPeriod).where(EvaluationPeriod.status == PeriodStatus.open)
    )
    # همان مهرهایی که مسیر تک‌رکوردی می‌زند (P1-04 و P1-05) — یک‌بار برای کل
    # دسته خوانده می‌شوند، پس همهٔ پرونده‌های یک اجرا زیر یک نسخه‌اند.
    scheme = active_scheme(db)
    framework = ensure_framework(db)
    access_by_person = {
        row.personnel_id: row
        for row in db.scalars(
            select(EvaluationAccess).where(
                EvaluationAccess.personnel_id.in_(
                    [p.personnel_id for p in plans if p.outcome is BulkOutcome.created]
                )
            )
        )
    }

    for person_plan in plans:
        if person_plan.outcome is not BulkOutcome.created:
            continue
        access = access_by_person[person_plan.personnel_id]
        record = EvaluationRecord(
            evaluation_code=next_evaluation_code(db),
            subject_personnel_id=person_plan.personnel_id,
            unit_supervisor_user_id=(
                None if person_plan.manager_path else access.unit_supervisor_user_id
            ),
            deputy_user_id=access.deputy_user_id,
            ceo_user_id=access.ceo_user_id,
            period_id=open_period.id if open_period else None,
            scoring_scheme_id=scheme.id if scheme else None,
            indicator_framework_id=framework.id,
            status=(
                EvaluationStatus.hr_approved
                if person_plan.manager_path
                else EvaluationStatus.draft
            ),
        )
        # savepoint تودرتو: اگر ایندکس یکتای جزئی این ردیف را رد کند، فقط همین
        # ردیف برمی‌گردد و بقیهٔ کار دست‌نخورده می‌ماند.
        nested = db.begin_nested()
        try:
            db.add(record)
            db.flush()
            nested.commit()
            person_plan.evaluation_id = record.id
            person_plan.evaluation_code = record.evaluation_code
        except IntegrityError:
            nested.rollback()
            # مسابقه با یک ارزیابِ دیگر که همین لحظه دستی شروع کرده. گارد کار کرده
            # است؛ فقط باید صادقانه گزارش شود.
            person_plan.outcome = BulkOutcome.blocked_conflict

    return plans


def summarise(plans: list[PersonPlan]) -> dict[str, int]:
    """شمارش به تفکیک نتیجه — همان چیزی که در لاگ ممیزی ثبت می‌شود."""
    counts: dict[str, int] = {}
    for person_plan in plans:
        counts[person_plan.outcome.value] = counts.get(person_plan.outcome.value, 0) + 1
    return counts
