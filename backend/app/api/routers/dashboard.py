from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy import true as sa_true
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.api.routers.personnel import _can_view_personnel
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.enums import EvaluationStatus, IndicatorSection, PersonnelStatus, UserRole
from app.models.evaluation import EvaluationRecord, EvaluationScore
from app.models.evaluation_access import EvaluationAccess
from app.models.evaluation_period import EvaluationPeriod
from app.models.indicator import Indicator
from app.models.personnel import Personnel
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.schemas.dashboard import (
    DashboardOverview,
    EvaluatorStat,
    IndicatorStat,
    InProgressEvaluation,
    OutcomeMix,
    PeriodTrendPoint,
    PersonStat,
    PipelineStat,
    RadarPoint,
    RoleOverview,
    RoleOverviewCard,
    StageStat,
    TrendPoint,
    UnitStat,
)
from app.schemas.notification import ExpiringContract
from app.services.org_unit import site_of, units_in_site
from app.services.privacy import suppressed_avg
from app.services.scoring_scheme import current_rules
from app.services.stage_stats import stage_stats
from app.services.workflow import IS_OPEN_RECORD

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

_FINALIZED = EvaluationRecord.status == EvaluationStatus.finalized

# قیف «پیشرفت» را نشان می‌دهد، پس cancelled عمداً در آن نیست: پروندهٔ لغوشده به
# مرحلهٔ بعد نمی‌رود و آوردنش در قیف، نرخ عبور را مخدوش می‌کند. HR پرونده‌های لغوشده
# را از فهرست ارزیابی‌ها با فیلتر وضعیت می‌بیند.
_PIPELINE_STATUSES: tuple[EvaluationStatus, ...] = (
    EvaluationStatus.draft,
    EvaluationStatus.submitted,
    EvaluationStatus.hr_approved,
    EvaluationStatus.deputy_approved,
    EvaluationStatus.finalized,
)


def _outcome_mix(db: Session, in_site) -> OutcomeMix:
    """چند درصد افراد «مطلوب»اند و چند درصد «نیازمند بهبود».

    هر دو مرز از خودِ طرحِ نمره‌دهیِ فعال می‌آیند:

    * **نیازمند بهبود** = همان بازه‌ای که سامانه برایش برنامهٔ بهبود می‌سازد
      (`improvement_plan_max_pct`). یعنی این درصد دقیقاً می‌گوید برای چند نفر
      باید برنامه نوشت — نه یک عددِ تعریف‌نشده.
    * **مطلوب** = بالاترین بندِ همان طرح.

    عددِ ثابت در کد یعنی سازمانی که قواعدش را عوض می‌کند، گزارشی می‌بیند که با
    قواعد خودش نمی‌خواند.

    شمارش روی *افراد* است نه پرونده‌ها، و برای هر فرد آخرین پروندهٔ نهایی‌شده‌اش
    حساب می‌شود: کسی که پارسال ضعیف بوده و امسال خوب، امروز «نیازمند بهبود»
    نیست.
    """
    rules = current_rules(db)
    improvement_threshold = float(rules.improvement_plan_max_pct)
    # `thresholds` سقف‌های بازه‌اند؛ سقفِ یکی‌مانده‌به‌آخر، کفِ بالاترین بند است.
    strong_threshold = (
        float(rules.thresholds[-2][0]) if len(rules.thresholds) >= 2 else improvement_threshold
    )

    latest = (
        select(
            EvaluationRecord.subject_personnel_id.label("pid"),
            EvaluationRecord.final_weighted_pct.label("pct"),
            func.row_number()
            .over(
                partition_by=EvaluationRecord.subject_personnel_id,
                order_by=EvaluationRecord.finalized_at.desc().nullslast(),
            )
            .label("rank"),
        )
        .where(_FINALIZED, in_site, EvaluationRecord.final_weighted_pct.is_not(None))
        .subquery()
    )
    rows = db.execute(select(latest.c.pct).where(latest.c.rank == 1)).all()
    people = len(rows)
    if people == 0:
        return OutcomeMix(
            strong_pct=None,
            needs_improvement_pct=None,
            strong_threshold_pct=strong_threshold,
            improvement_threshold_pct=improvement_threshold,
            people_counted=0,
        )

    strong = sum(1 for (pct,) in rows if float(pct) >= strong_threshold)
    weak = sum(1 for (pct,) in rows if float(pct) <= improvement_threshold)
    return OutcomeMix(
        strong_pct=round(strong * 100 / people, 1),
        needs_improvement_pct=round(weak * 100 / people, 1),
        strong_threshold_pct=strong_threshold,
        improvement_threshold_pct=improvement_threshold,
        people_counted=people,
    )


def _units_of(db: Session, site: str | None) -> list[str] | None:
    """واحدهای زیر یک محل، یا `None` یعنی «بدون فیلتر».

    `None` و نه فهرست خالی: فهرست خالی به `IN ()` تبدیل می‌شود و همه‌چیز را حذف
    می‌کند — یعنی «همهٔ محل‌ها» و «محلی که کسی در آن نیست» یک نتیجه می‌دادند.
    """
    if not site:
        return None
    return units_in_site(list(db.scalars(select(Personnel.org_unit).distinct())), site)


@router.get("/overview", response_model=DashboardOverview)
def overview(
    site: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> DashboardOverview:
    """همه آمارها با تجمیع SQL محاسبه می‌شوند؛ نسخه قبلی کل جدول‌ها را در حافظه
    بارگذاری می‌کرد و به ازای هر رکورد یک کوئری جدا برای امتیازها می‌زد (N+1)."""
    # فیلتر محل روی *کل* این نما اعمال می‌شود، نه فقط روی سه عدد بالا. فیلتری که
    # نیمی از صفحه را عوض کند و نیمی را نه، خواننده را وادار می‌کند هر بار بپرسد
    # کدام عدد فیلتر شده — که بدتر از نداشتنِ فیلتر است.
    units = _units_of(db, site)
    in_site = (
        EvaluationRecord.subject_personnel_id.in_(
            select(Personnel.id).where(Personnel.org_unit.in_(units))
        )
        if units is not None
        else sa_true()
    )

    total = (
        db.scalar(
            select(func.count()).select_from(EvaluationRecord).where(_FINALIZED, in_site)
        )
        or 0
    )
    avg_raw = db.scalar(
        select(func.avg(EvaluationRecord.final_weighted_pct)).where(_FINALIZED, in_site)
    )
    avg_final = round(float(avg_raw), 1) if avg_raw is not None else None

    unit_rows = db.execute(
        select(
            Personnel.org_unit,
            func.avg(EvaluationRecord.final_weighted_pct),
            # دو بخشِ فرم جدا می‌آیند: واحدی که نمرهٔ کلش خوب است ممکن است در
            # یکی از دو بخش ضعیف باشد و در دیگری قوی — عددِ کل آن را پنهان می‌کند.
            func.avg(EvaluationRecord.general_score_pct),
            func.avg(EvaluationRecord.specialized_score_pct),
            func.count(),
        )
        .join(Personnel, Personnel.id == EvaluationRecord.subject_personnel_id)
        .where(_FINALIZED, in_site, EvaluationRecord.final_weighted_pct.is_not(None))
        .group_by(Personnel.org_unit)
    ).all()
    by_org_unit = [
        UnitStat(
            org_unit=unit,
            avg_final_pct=suppressed_avg(round(float(avg), 1), count),
            # همان سرکوبِ کوهورت روی هر سه عدد: اگر فقط کل سرکوب می‌شد، دو عددِ
            # جزء همان چیزی را لو می‌دادند که سرکوب برای پنهان‌کردنش هست.
            avg_general_pct=(
                suppressed_avg(round(float(general), 1), count) if general is not None else None
            ),
            avg_specialized_pct=(
                suppressed_avg(round(float(specialized), 1), count)
                if specialized is not None
                else None
            ),
            site=site_of(unit),
            count=count,
        )
        for unit, avg, general, specialized, count in unit_rows
    ]

    subordinate_counts = dict(
        db.execute(
            select(EvaluationAccess.unit_supervisor_user_id, func.count())
            .where(EvaluationAccess.unit_supervisor_user_id.is_not(None))
            .group_by(EvaluationAccess.unit_supervisor_user_id)
        ).all()
    )

    evaluator_rows = db.execute(
        select(
            User.id,
            User.username,
            User.full_name,
            func.avg(EvaluationRecord.final_weighted_pct),
            func.count(),
        )
        .join(EvaluationRecord, EvaluationRecord.unit_supervisor_user_id == User.id)
        .where(_FINALIZED, in_site, EvaluationRecord.final_weighted_pct.is_not(None))
        .group_by(User.id, User.username, User.full_name)
    ).all()
    by_evaluator = [
        EvaluatorStat(
            evaluator_user_id=uid,
            username=username,
            full_name=full_name,
            # میانگین یک ارزیاب که فقط دو پرونده داده، پروفایل او نیست — امتیاز همان
            # دو نفر است. تحلیل رفتار ارزیاب به دادهٔ کافی نیاز دارد.
            avg_final_pct=suppressed_avg(round(float(avg), 1), count),
            subordinate_count=subordinate_counts.get(uid, 0),
            evaluation_count=count,
        )
        for uid, username, full_name, avg, count in evaluator_rows
    ]

    def _indicator_stats(section: IndicatorSection | None, *, weakest: bool) -> list[IndicatorStat]:
        """پنج شاخصِ ضعیف یا قوی، در یک بخشِ فرم یا در کل آن.

        «قوی‌ترین‌ها» به‌اندازهٔ «ضعیف‌ترین‌ها» لازم است: فهرستی که فقط ضعف نشان
        می‌دهد، هر سازمانی را بیمار جلوه می‌دهد و هیچ‌وقت نمی‌گوید کجا باید همان
        کار را تکرار کرد.
        """
        query = (
            select(
                Indicator.id,
                Indicator.category,
                Indicator.description,
                func.avg(EvaluationScore.score),
                func.count(),
            )
            .join(EvaluationScore, EvaluationScore.indicator_id == Indicator.id)
            .join(EvaluationRecord, EvaluationRecord.id == EvaluationScore.evaluation_record_id)
            .where(_FINALIZED, in_site)
            .group_by(Indicator.id, Indicator.category, Indicator.description)
            .order_by(func.avg(EvaluationScore.score) if weakest else func.avg(EvaluationScore.score).desc())
            .limit(5)
        )
        if section is not None:
            query = query.where(Indicator.section == section)
        return [
            IndicatorStat(
                indicator_id=iid,
                category=category,
                description=description,
                avg_score=suppressed_avg(round(float(avg), 2), count),
            )
            for iid, category, description, avg, count in db.execute(query).all()
        ]

    lowest_by_indicator = _indicator_stats(IndicatorSection.general, weakest=True)
    highest_by_indicator = _indicator_stats(IndicatorSection.general, weakest=False)
    lowest_by_specialized_indicator = _indicator_stats(IndicatorSection.specialized, weakest=True)
    highest_by_specialized_indicator = _indicator_stats(IndicatorSection.specialized, weakest=False)

    # «۵ واحد ضعیف‌تر» فقط از میان واحدهایی انتخاب می‌شود که میانگینشان قابل نمایش
    # است؛ رتبه‌بندی روی مقدار سرکوب‌شده هم بی‌معناست و هم خود سرکوب را دور می‌زند
    # (جایگاه در فهرست «ضعیف‌ترین‌ها» خودش یک نشت است).
    lowest_by_unit = sorted(
        (u for u in by_org_unit if u.avg_final_pct is not None),
        key=lambda x: x.avg_final_pct,
    )[:5]

    # ۲۰ نفر و نه ۵: این فهرست حالا در رابط بر اساس محل فیلتر می‌شود، و اگر فقط
    # ۵ نفرِ اولِ کل سازمان بیایند، فیلترِ «کارخانه» ممکن است هیچ‌کس را نشان ندهد
    # در حالی که کارخانه پرِ آدمِ نیازمندِ توجه است.
    person_rows = db.execute(
        select(
            Personnel.id,
            Personnel.full_name,
            Personnel.org_unit,
            EvaluationRecord.final_weighted_pct,
        )
        .join(Personnel, Personnel.id == EvaluationRecord.subject_personnel_id)
        .where(_FINALIZED, in_site, EvaluationRecord.final_weighted_pct.is_not(None))
        .order_by(EvaluationRecord.final_weighted_pct)
        .limit(20)
    ).all()
    lowest_by_person = [
        PersonStat(
            personnel_id=pid,
            full_name=name,
            org_unit=unit,
            site=site_of(unit),
            final_weighted_pct=float(pct),
        )
        for pid, name, unit, pct in person_rows
    ]

    return DashboardOverview(
        total_evaluations=total,
        avg_final_pct=avg_final,
        outcome_mix=_outcome_mix(db, in_site),
        by_org_unit=by_org_unit,
        by_evaluator=by_evaluator,
        lowest_by_indicator=lowest_by_indicator,
        highest_by_indicator=highest_by_indicator,
        lowest_by_specialized_indicator=lowest_by_specialized_indicator,
        highest_by_specialized_indicator=highest_by_specialized_indicator,
        lowest_by_unit=lowest_by_unit,
        lowest_by_person=lowest_by_person,
    )


@router.get("/pipeline", response_model=list[PipelineStat])
def pipeline(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> list[PipelineStat]:
    """قیف گردش‌کار: چند پرونده در هر وضعیت است و قدیمی‌ترین پرونده هر وضعیت از کی مانده."""
    rows = {
        status_value: (count, oldest)
        for status_value, count, oldest in db.execute(
            select(
                EvaluationRecord.status,
                func.count(),
                func.min(EvaluationRecord.created_at),
            ).group_by(EvaluationRecord.status)
        ).all()
    }
    return [
        PipelineStat(
            status=status_member,
            count=rows.get(status_member, (0, None))[0],
            oldest_created_at=rows.get(status_member, (0, None))[1],
        )
        for status_member in _PIPELINE_STATUSES
    ]


@router.get("/period-trend", response_model=list[PeriodTrendPoint])
def period_trend(
    site: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> list[PeriodTrendPoint]:
    """روند میانگین سازمان، دوره به دوره.

    یک عددِ امروز نمی‌گوید سازمان دارد بهتر می‌شود یا بدتر؛ سه عدد پشت سر هم
    می‌گویند.

    پرونده‌های بدون دوره در یک ردیفِ جدا جمع می‌شوند و آخر می‌آیند — نه اینکه
    حذف شوند. حذفشان یعنی نموداری که ادعا می‌کند کل سازمان است ولی بخشی از
    ارزیابی‌ها را نمی‌شمارد، و کسی که آن را می‌خواند دلیلِ اختلاف را نمی‌فهمد.
    """
    units = _units_of(db, site)
    in_site = (
        EvaluationRecord.subject_personnel_id.in_(
            select(Personnel.id).where(Personnel.org_unit.in_(units))
        )
        if units is not None
        else sa_true()
    )

    rows = db.execute(
        select(
            EvaluationPeriod.id,
            EvaluationPeriod.name,
            EvaluationPeriod.starts_on,
            func.avg(EvaluationRecord.final_weighted_pct),
            func.count(),
        )
        .select_from(EvaluationRecord)
        .outerjoin(EvaluationPeriod, EvaluationPeriod.id == EvaluationRecord.period_id)
        .where(_FINALIZED, in_site, EvaluationRecord.final_weighted_pct.is_not(None))
        .group_by(EvaluationPeriod.id, EvaluationPeriod.name, EvaluationPeriod.starts_on)
        .order_by(EvaluationPeriod.starts_on.nullslast())
    ).all()

    return [
        PeriodTrendPoint(
            period_id=period_id,
            name=name or "بدون دوره",
            starts_on=starts_on,
            avg_final_pct=suppressed_avg(round(float(avg), 1), count),
            count=count,
        )
        for period_id, name, starts_on, avg, count in rows
    ]


@router.get("/stage-stats", response_model=list[StageStat])
def stage_statistics(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> list[StageStat]:
    """وضعیت پرونده‌ها در هر مرحله، با زمان توقف و تفکیک به‌ازای هر مسئول.

    جانشین «قیف گردش‌کار» که فقط یک عدد در هر مرحله می‌داد. آن عدد می‌گفت کجا
    شلوغ است ولی نه چرا: صفِ ده‌تایی که هر پرونده‌اش نیم روز می‌ماند سالم است، و
    صفِ دوتایی که هر کدام دو هفته مانده‌اند نیست.
    """
    return [StageStat(**row) for row in stage_stats(db)]


@router.get("/expiring-contracts", response_model=list[ExpiringContract])
def expiring_contracts(
    days: int = Query(default=60, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.hr)),
) -> list[ExpiringContract]:
    """پرسنل فعالی که قراردادشان تا N روز آینده تمام می‌شود (یا منقضی شده)، به‌همراه
    این‌که آیا ارزیابی بازی برایشان در جریان است — هدف اصلی محصول: تصمیم به‌موقع تمدید."""
    today = date.today()
    horizon = today + timedelta(days=days)

    open_evaluation_exists = (
        select(EvaluationRecord.id)
        .where(
            EvaluationRecord.subject_personnel_id == Personnel.id,
            IS_OPEN_RECORD,
        )
        .exists()
    )

    rows = db.execute(
        select(
            Personnel.id,
            Personnel.full_name,
            Personnel.org_unit,
            Personnel.contract_end_date,
            open_evaluation_exists.label("has_open"),
        )
        .where(
            Personnel.status == PersonnelStatus.active,
            Personnel.contract_end_date <= horizon,
        )
        .order_by(Personnel.contract_end_date)
    ).all()

    return [
        ExpiringContract(
            personnel_id=pid,
            full_name=name,
            org_unit=unit,
            contract_end_date=end_date,
            days_remaining=(end_date - today).days,
            has_open_evaluation=has_open,
        )
        for pid, name, unit, end_date, has_open in rows
    ]


@router.get("/personnel/{personnel_id}/radar", response_model=list[RadarPoint])
def personnel_radar(
    personnel_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[RadarPoint]:
    # HR همه را می‌بیند؛ ارزیاب‌ها (مسئول واحد/معاونت/مدیرعامل) فقط پرسنلی را که
    # در حوزهٔ دسترسی/ارزیابی خودشان است — تا پیش از نمره‌دهی روند فرد را ببینند.
    if not _can_view_personnel(db, personnel_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="دسترسی مجاز نیست")
    rows = db.execute(
        select(Indicator.category, func.avg(EvaluationScore.score))
        .join(EvaluationScore, EvaluationScore.indicator_id == Indicator.id)
        .join(EvaluationRecord, EvaluationRecord.id == EvaluationScore.evaluation_record_id)
        .where(_FINALIZED, EvaluationRecord.subject_personnel_id == personnel_id)
        .group_by(Indicator.category)
    ).all()
    return [RadarPoint(category=category, avg_score=round(float(avg), 2)) for category, avg in rows]


@router.get("/personnel/{personnel_id}/trend", response_model=list[TrendPoint])
def personnel_trend(
    personnel_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[TrendPoint]:
    if not _can_view_personnel(db, personnel_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="دسترسی مجاز نیست")
    records = db.scalars(
        select(EvaluationRecord)
        .where(
            _FINALIZED,
            EvaluationRecord.subject_personnel_id == personnel_id,
            EvaluationRecord.finalized_at.is_not(None),
        )
        .order_by(EvaluationRecord.finalized_at)
    )
    return [
        TrendPoint(
            evaluation_code=r.evaluation_code,
            finalized_at=r.finalized_at.isoformat(),
            final_weighted_pct=float(r.final_weighted_pct),
        )
        for r in records
    ]


@router.get(
    "/personnel/{personnel_id}/in-progress",
    response_model=InProgressEvaluation | None,
)
def personnel_in_progress(
    personnel_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> InProgressEvaluation | None:
    """ارزیابی باز (نهایی‌نشدهٔ) جاری این پرسنل را برمی‌گرداند تا در پروفایل، «مرحلهٔ
    فعلی» نمایش داده شود؛ اگر پرونده‌ای در جریان نباشد null برمی‌گردد. دسترسی مثل
    رادار/روند محدود است (HR همه، ارزیاب فقط حوزهٔ خودش)."""
    if not _can_view_personnel(db, personnel_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="دسترسی مجاز نیست")
    record = db.scalar(
        select(EvaluationRecord)
        .where(
            EvaluationRecord.subject_personnel_id == personnel_id,
            IS_OPEN_RECORD,
        )
        .order_by(EvaluationRecord.created_at.desc())
    )
    if record is None:
        return None
    was_returned = (
        db.scalar(
            select(AuditLog.id)
            .where(
                AuditLog.event_type == "evaluation_returned",
                AuditLog.evaluation_record_id == record.id,
            )
            .limit(1)
        )
        is not None
    )
    return InProgressEvaluation(
        evaluation_id=record.id,
        evaluation_code=record.evaluation_code,
        status=record.status,
        was_returned=was_returned,
        created_at=record.created_at,
    )


def _count_records(db: Session, *conditions) -> int:
    return (
        db.scalar(
            select(func.count()).select_from(EvaluationRecord).where(*conditions)
        )
        or 0
    )


#: ارقام فارسی برای متن‌هایی که مستقیم نمایش داده می‌شوند. بقیهٔ اعداد در
#: فرانت‌اند با `toLocaleString("fa-IR")` قالب می‌گیرند؛ این‌جا چون رشته از
#: سرور می‌آید، همان‌جا هم قالب می‌گیرد.
_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa(value: int) -> str:
    return str(value).translate(_FA_DIGITS)


@router.get("/role-overview", response_model=RoleOverview)
def role_overview(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RoleOverview:
    """کاشی‌های خلاصهٔ داشبورد، متناسب با نقشِ کاربرِ واردشده — تا هر نقش در صفحهٔ
    اصلی خود یک نمای سریع از کارهای در انتظار و وضعیت پرونده‌هایش داشته باشد."""
    uid = current_user.id
    role = current_user.role
    cards: list[RoleOverviewCard] = []

    if role == UserRole.unit_supervisor:
        subordinates = (
            db.scalar(
                select(func.count())
                .select_from(EvaluationAccess)
                .where(EvaluationAccess.unit_supervisor_user_id == uid)
            )
            or 0
        )
        mine = EvaluationRecord.unit_supervisor_user_id == uid
        cards = [
            RoleOverviewCard(key="subordinates", label="افراد زیرمجموعه", value=subordinates, tone="neutral"),
            RoleOverviewCard(
                key="drafts",
                label="پیش‌نویس باز",
                value=_count_records(db, mine, EvaluationRecord.status == EvaluationStatus.draft),
                tone="amber",
            ),
            RoleOverviewCard(
                key="in_review",
                label="در جریان تأیید",
                value=_count_records(
                    db,
                    mine,
                    EvaluationRecord.status.in_(
                        [
                            EvaluationStatus.submitted,
                            EvaluationStatus.hr_approved,
                            EvaluationStatus.deputy_approved,
                        ]
                    ),
                ),
                tone="pulse",
            ),
            RoleOverviewCard(
                key="finalized",
                label="نهایی‌شده",
                value=_count_records(db, mine, _FINALIZED),
                tone="green",
            ),
        ]
    elif role == UserRole.deputy:
        mine = EvaluationRecord.deputy_user_id == uid
        cards = [
            RoleOverviewCard(
                key="awaiting_me",
                label="در انتظار تأیید من",
                value=_count_records(
                    db,
                    mine,
                    EvaluationRecord.status == EvaluationStatus.hr_approved,
                    EvaluationRecord.unit_supervisor_user_id.is_not(None),
                ),
                tone="amber",
            ),
            RoleOverviewCard(
                key="manager_scoring",
                label="امتیازدهی مدیر (با من)",
                value=_count_records(
                    db,
                    mine,
                    EvaluationRecord.status == EvaluationStatus.hr_approved,
                    EvaluationRecord.unit_supervisor_user_id.is_(None),
                ),
                tone="pulse",
            ),
            RoleOverviewCard(
                key="finalized",
                label="نهایی‌شده (حوزهٔ من)",
                value=_count_records(db, mine, _FINALIZED),
                tone="green",
            ),
        ]
    elif role == UserRole.ceo:
        mine = EvaluationRecord.ceo_user_id == uid
        cards = [
            RoleOverviewCard(
                key="awaiting_me",
                label="در انتظار تأیید نهایی",
                value=_count_records(
                    db, mine, EvaluationRecord.status == EvaluationStatus.deputy_approved
                ),
                tone="amber",
            ),
            RoleOverviewCard(
                key="finalized",
                label="نهایی‌شده (حوزهٔ من)",
                value=_count_records(db, mine, _FINALIZED),
                tone="green",
            ),
            RoleOverviewCard(
                key="total",
                label="کل پرونده‌های من",
                value=_count_records(db, mine),
                tone="neutral",
            ),
        ]
    elif role == UserRole.hr:
        # «مشمول ارزیابی» یعنی پرسنلِ فعال. کسی که از سازمان رفته در مخرجِ پوشش
        # جایی ندارد — وگرنه درصد تکمیل هیچ‌وقت به صد نمی‌رسد و عددی می‌شود که
        # هیچ‌کس دنبالش نیست.
        eligible = (
            db.scalar(
                select(func.count())
                .select_from(Personnel)
                .where(Personnel.status == PersonnelStatus.active)
            )
            or 0
        )
        finalized_count = _count_records(db, _FINALIZED)
        # پرسنل شمرده می‌شود، نه پرونده: کسی که دو پروندهٔ نهایی‌شده دارد (دورهٔ
        # قبل و امسال) نباید پوشش را دو برابر نشان بدهد.
        covered = (
            db.scalar(
                select(func.count(func.distinct(EvaluationRecord.subject_personnel_id))).where(
                    _FINALIZED
                )
            )
            or 0
        )
        cards = [
            RoleOverviewCard(
                key="eligible",
                label="کل پرسنل مشمول ارزیابی",
                value=eligible,
                tone="neutral",
            ),
            RoleOverviewCard(
                key="awaiting_hr",
                label="در انتظار بررسی منابع انسانی",
                value=_count_records(db, EvaluationRecord.status == EvaluationStatus.submitted),
                tone="amber",
            ),
            RoleOverviewCard(
                key="finalized",
                label="نهایی‌شده",
                value=finalized_count,
                tone="green",
            ),
            RoleOverviewCard(
                key="completion",
                label="درصد تکمیل",
                value=round(covered * 100 / eligible, 1) if eligible else 0,
                # خنثی و نه قرمز: پوششِ ناقص وضعیتی است که باید دیده شود، نه
                # هشداری که باید ترساند — و قرمز در این رابط معنای کنش دارد.
                tone="neutral",
                suffix="٪",
                hint=f"{_fa(covered)} از {_fa(eligible)} نفر",
            ),
        ]
    elif role == UserRole.employee and current_user.personnel_id is not None:
        pid = current_user.personnel_id
        mine = EvaluationRecord.subject_personnel_id == pid
        avg = db.scalar(
            select(func.avg(EvaluationRecord.final_weighted_pct)).where(mine, _FINALIZED)
        )
        cards = [
            RoleOverviewCard(
                key="finalized",
                label="ارزیابی‌های نهایی‌شده",
                value=_count_records(db, mine, _FINALIZED),
                tone="neutral",
            ),
            RoleOverviewCard(
                key="avg",
                label="میانگین امتیاز نهایی (٪)",
                value=round(float(avg), 1) if avg is not None else 0,
                tone="green",
            ),
            RoleOverviewCard(
                key="pending_ack",
                # «رؤیت» در گفتار اداری یعنی «دیدم»، ولی کارمند آن را «قبول
                # دارم» می‌خواند. متن‌های رو به کارمند عمداً از این واژه پرهیز
                # می‌کنند؛ برچسب‌های لاگ ممیزی که HR می‌خواند دست‌نخورده‌اند.
                label="هنوز ندیده‌اید",
                value=_count_records(
                    db, mine, _FINALIZED, EvaluationRecord.acknowledged_at.is_(None)
                ),
                tone="amber",
            ),
        ]

    return RoleOverview(role=role.value, cards=cards)
