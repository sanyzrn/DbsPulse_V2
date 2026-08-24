from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.enums import EvaluationStatus, PeriodStatus, PersonnelStatus, UserRole
from app.models.evaluation import EvaluationRecord
from app.models.evaluation_access import EvaluationAccess
from app.models.evaluation_period import EvaluationPeriod
from app.models.personnel import Personnel
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.schemas.period import (
    BulkCreateRequest,
    BulkCreateResult,
    BulkPersonResult,
    NotStartedPersonnel,
    PeriodCreate,
    PeriodProgress,
    PeriodRead,
)
from app.services.audit import log_event
from app.services.bulk_evaluation import BulkOutcome, CohortFilter, execute, plan, summarise
from app.services.notifications import notify
from app.services.workflow import IS_OPEN_RECORD

router = APIRouter(prefix="/api/periods", tags=["periods"])

# سقف فهرست «شروع‌نشده‌ها». تعداد کل جداگانه برگردانده می‌شود، پس بریدن فهرست
# چیزی را پنهان نمی‌کند — فقط جلوی پاسخِ چندهزارردیفی را می‌گیرد.
NOT_STARTED_LIMIT = 200


def _get_period_or_404(db: Session, period_id: int) -> EvaluationPeriod:
    period = db.get(EvaluationPeriod, period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="دوره ارزیابی یافت نشد")
    return period


@router.get("", response_model=list[PeriodRead])
def list_periods(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> list[EvaluationPeriod]:
    return list(
        db.scalars(select(EvaluationPeriod).order_by(EvaluationPeriod.created_at.desc()))
    )


@router.post("", response_model=PeriodRead, status_code=status.HTTP_201_CREATED)
def create_period(
    payload: PeriodCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> EvaluationPeriod:
    already_open = db.scalar(
        select(EvaluationPeriod).where(EvaluationPeriod.status == PeriodStatus.open)
    )
    if already_open is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"دوره «{already_open.name}» هنوز باز است؛ ابتدا آن را ببندید",
        )

    period = EvaluationPeriod(
        name=payload.name,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        status=PeriodStatus.open,
        created_by_user_id=current_user.id,
    )
    db.add(period)
    try:
        db.flush()
    except IntegrityError as exc:
        # دو درخواست هم‌زمان: ایندکس یکتای جزئی برنده را مشخص می‌کند
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="یک دوره باز دیگر هم‌زمان ساخته شد؛ ابتدا آن را ببندید",
        ) from exc

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="period_created",
        new_value={"id": period.id, "name": period.name},
    )
    # ارزیاب‌ها (مسئولان واحد و معاونت‌ها) از شروع دوره باخبر می‌شوند
    evaluator_ids = db.scalars(
        select(User.id).where(
            User.role.in_([UserRole.unit_supervisor, UserRole.deputy]),
            User.is_active.is_(True),
        )
    )
    notify(
        db,
        evaluator_ids,
        type_="period_opened",
        message=f"دوره ارزیابی «{period.name}» آغاز شد؛ ارزیابی افراد زیرمجموعه خود را شروع کنید",
        link="/",
    )
    db.commit()
    db.refresh(period)
    return period


@router.post("/{period_id}/close", response_model=PeriodRead)
def close_period(
    period_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> EvaluationPeriod:
    period = _get_period_or_404(db, period_id)
    if period.status != PeriodStatus.open:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="این دوره قبلاً بسته شده است"
        )

    # بستنِ دوره‌ای که پروندهٔ باز دارد، تا امروز بی‌صدا انجام می‌شد: وضعیت عوض
    # می‌شد و آن پرونده‌ها همان‌طور در گردش‌کار می‌ماندند تا ماه‌ها بعد زیر یک
    # دورهٔ بسته نهایی شوند. «بستن» چیزی را نبسته بود.
    #
    # جلوگیریِ مطلق هم درست نیست: گاهی واقعاً باید دوره را بست و آن چند پرونده
    # را جدا پیش برد. پس تصمیم به تصمیم‌گیرنده برمی‌گردد — ولی صریح، نه ضمنی.
    open_cases = (
        db.scalar(
            select(func.count())
            .select_from(EvaluationRecord)
            .where(EvaluationRecord.period_id == period_id, IS_OPEN_RECORD)
        )
        or 0
    )
    if open_cases and not force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    f"این دوره {open_cases} پروندهٔ باز دارد. اگر دوره بسته شود، آن‌ها "
                    "در گردش‌کار می‌مانند و بعداً زیر یک دورهٔ بسته نهایی می‌شوند. "
                    "برای بستنِ آگاهانه، درخواست را با force تکرار کنید."
                ),
                "open_cases": open_cases,
            },
        )

    period.status = PeriodStatus.closed
    period.closed_at = datetime.now(UTC)
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="period_closed",
        # عددِ پرونده‌های باز در لحظهٔ بستن ثبت می‌شود: «آگاهانه بسته شد» فقط
        # وقتی معنا دارد که بشود گفت چه چیزی معلوم بوده.
        new_value={"id": period.id, "name": period.name, "open_cases": open_cases},
    )
    db.commit()
    db.refresh(period)
    return period


@router.get("/{period_id}/progress", response_model=PeriodProgress)
def period_progress(
    period_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> PeriodProgress:
    period = _get_period_or_404(db, period_id)

    # واجدان دوره = هر پرسنل فعال. نه «هر پرسنل فعالی که زنجیره دارد».
    #
    # تفاوتش تمام ماجراست: با شرطِ زنجیره، کسی که زنجیره‌اش تنظیم نشده از *مخرج*
    # حذف می‌شد، پس پوشش می‌توانست ۱۰۰٪ نشان بدهد در حالی که ده نفر ارزیابی
    # نشده‌اند. داشبوردی که به‌خاطر دادهٔ ناقص عدد بهتری نشان می‌دهد، از نبودنش
    # بدتر است — چون کسی دنبال آن ده نفر نمی‌رود.
    eligible = (
        db.scalar(
            select(func.count())
            .select_from(Personnel)
            .where(Personnel.status == PersonnelStatus.active)
        )
        or 0
    )

    # و همان‌ها که کنار گذاشته می‌شدند، حالا صریحاً شمرده می‌شوند: تا زنجیره‌شان
    # تنظیم نشود، هیچ‌کس نمی‌تواند ارزیابی‌شان کند.
    without_chain_query = (
        select(Personnel.id, Personnel.full_name, Personnel.org_unit)
        .outerjoin(EvaluationAccess, EvaluationAccess.personnel_id == Personnel.id)
        .where(
            Personnel.status == PersonnelStatus.active,
            EvaluationAccess.id.is_(None),
        )
    )
    without_chain_total = (
        db.scalar(select(func.count()).select_from(without_chain_query.subquery())) or 0
    )
    without_chain_rows = db.execute(
        without_chain_query.order_by(Personnel.full_name).limit(NOT_STARTED_LIMIT)
    ).all()

    started = (
        db.scalar(
            select(func.count())
            .select_from(EvaluationRecord)
            .where(EvaluationRecord.period_id == period_id)
        )
        or 0
    )
    finalized = (
        db.scalar(
            select(func.count())
            .select_from(EvaluationRecord)
            .where(
                EvaluationRecord.period_id == period_id,
                EvaluationRecord.status == EvaluationStatus.finalized,
            )
        )
        or 0
    )

    # پرونده‌های همین دوره که هنوز وسط گردش‌کارند. عمداً «started - finalized»
    # حساب نمی‌شود: پرونده‌های لغوشده نه بازند نه نهایی، و آن تفریق آن‌ها را هم
    # «در جریان» نشان می‌داد.
    in_progress = (
        db.scalar(
            select(func.count())
            .select_from(EvaluationRecord)
            .where(EvaluationRecord.period_id == period_id, IS_OPEN_RECORD)
        )
        or 0
    )

    has_period_evaluation = (
        select(EvaluationRecord.id)
        .where(
            EvaluationRecord.subject_personnel_id == Personnel.id,
            EvaluationRecord.period_id == period_id,
        )
        .exists()
    )
    # این فهرست هم به همان دلیل دیگر با «زنجیره دارد» فیلتر نمی‌شود: کسی که
    # زنجیره ندارد، مصداقِ کامل «شروع نشده» است، نه مصداقِ «به من مربوط نیست».
    not_started_query = (
        select(Personnel.id, Personnel.full_name, Personnel.org_unit)
        .where(Personnel.status == PersonnelStatus.active, ~has_period_evaluation)
    )
    not_started_total = (
        db.scalar(select(func.count()).select_from(not_started_query.subquery())) or 0
    )
    not_started_rows = db.execute(
        not_started_query.order_by(Personnel.full_name).limit(NOT_STARTED_LIMIT)
    ).all()

    return PeriodProgress(
        period=PeriodRead.model_validate(period),
        eligible=eligible,
        started=started,
        finalized=finalized,
        in_progress=in_progress,
        not_started_total=not_started_total,
        without_chain_total=without_chain_total,
        without_chain=[
            NotStartedPersonnel(personnel_id=pid, full_name=name, org_unit=unit)
            for pid, name, unit in without_chain_rows
        ],
        not_started=[
            NotStartedPersonnel(personnel_id=pid, full_name=name, org_unit=unit)
            for pid, name, unit in not_started_rows
        ],
    )


def _to_cohort(payload: BulkCreateRequest) -> CohortFilter:
    return CohortFilter(
        org_unit=payload.org_unit,
        only_managers=payload.only_managers,
        contract_ends_before=payload.contract_ends_before,
    )


def _to_result(plans: list, *, dry_run: bool) -> BulkCreateResult:
    return BulkCreateResult(
        dry_run=dry_run,
        total=len(plans),
        counts=summarise(plans),
        results=[
            BulkPersonResult(
                personnel_id=p.personnel_id,
                full_name=p.full_name,
                org_unit=p.org_unit,
                outcome=p.outcome.value,
                reason=p.reason,
                evaluation_id=p.evaluation_id,
                evaluation_code=p.evaluation_code,
            )
            for p in plans
        ],
    )


@router.post("/bulk-create/preview", response_model=BulkCreateResult)
def preview_bulk_create(
    payload: BulkCreateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> BulkCreateResult:
    """اجرای خشک: دقیقاً می‌گوید برای چه کسانی ارزیابی ساخته می‌شود، چه کسانی رد
    می‌شوند و چرا — بدون اینکه چیزی نوشته شود (P2-03).

    این مرحله اختیاری نیست بلکه *نقطهٔ تصمیم* است: باز کردن یک چرخه برای دویست
    نفر کاری است که برگرداندنش دستی و پرزحمت است، پس باید بشود پیش از انجامش
    دیدش.
    """
    return _to_result(plan(db, _to_cohort(payload)), dry_run=True)


@router.post("/bulk-create", response_model=BulkCreateResult)
def run_bulk_create(
    payload: BulkCreateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> BulkCreateResult:
    """ساخت دسته‌ای، با گزارش سرنوشت هر نفر.

    منابع انسانی این کار را انجام می‌دهد، نه ارزیاب — و این عمدی است: باز کردن
    چرخه کارِ HR است، ولی هر پرونده در صف همان ارزیابی می‌نشیند که ردیف دسترسی
    نامش را برده. یعنی گاردِ «فقط مسئول واحد مربوطه می‌تواند شروع کند» در مسیر
    تک‌رکوردی سر جایش می‌ماند؛ این‌جا HR *به نمایندگی* چرخه را باز می‌کند و
    نمره‌دهی همچنان دست خودِ ارزیاب است.

    عملیات idempotent است: اجرای دوباره با همان کوهورت، برای کسانی که پرونده
    گرفته‌اند «از قبل باز دارد» برمی‌گرداند، نه پروندهٔ دوم.
    """
    plans = execute(db, _to_cohort(payload))
    result = _to_result(plans, dry_run=False)
    # ساخت دسته‌ای یک تصمیم سازمانی است، نه یک کلیک: چه کوهورتی و با چه نتیجه‌ای،
    # باید بعداً قابل بازخوانی باشد.
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="evaluations_bulk_created",
        new_value={
            "cohort": payload.model_dump(mode="json", exclude_none=True),
            "counts": result.counts,
        },
    )
    db.commit()

    # اعلان فقط به کسانی که واقعاً پرونده‌ای گرفته‌اند، و یکی به‌ازای هر نفر —
    # نه یکی به‌ازای هر پرونده، چون یک مسئول واحد ممکن است ده نفر بگیرد و ده
    # اعلانِ پشت‌سرهم یعنی هیچ اعلانی.
    created_by_assignee: dict[int, int] = {}
    for person_plan in plans:
        if person_plan.outcome is BulkOutcome.created and person_plan.assignee_user_id:
            created_by_assignee[person_plan.assignee_user_id] = (
                created_by_assignee.get(person_plan.assignee_user_id, 0) + 1
            )
    for user_id, count in created_by_assignee.items():
        notify(
            db,
            user_ids=[user_id],
            type_="bulk_evaluations_assigned",
            # متن به‌ازای هر گیرنده فرق دارد (تعدادِ خودش)، پس نمی‌شود یک notify
            # با فهرست گیرنده‌ها فرستاد.
            message=f"{count} ارزیابی جدید برای شما آغاز شد و منتظر نمره‌دهی است",
            link="/",
        )
    db.commit()
    return result
