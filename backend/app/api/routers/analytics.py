"""نماهای تحلیلیِ نقش‌محور (P2-01).

تا امروز تحلیل فقط برای منابع انسانی بود. نتیجه‌اش این بود که داده‌ای که سامانه
جمع می‌کند به تصمیم *یک* واحد کمک می‌کرد و نه هیچ‌کس دیگر:

* مسئول واحد نمی‌توانست ببیند توزیع نمره‌دهی خودش نسبت به سازمان کجاست — و این
  مفیدترین بازخوردی است که یک ارزیاب می‌تواند بگیرد. بدون آن، «سخت‌گیری» و
  «آسان‌گیری» یک شایعهٔ سازمانی می‌ماند، نه یک عدد قابل اصلاح.
* مدیرعامل یک صف می‌دید، نه نمایی از ریسک نیروی انسانی: کدام واحد عقب است، ترکیب
  توصیه‌ها به تمدید قرارداد چه می‌گوید، چرخهٔ تصمیم چقدر طول می‌کشد.

دو قاعدهٔ سخت که همهٔ این فایل رویشان بنا شده:

۱. **هیچ نامی در نمای مدیر ارشد نیست.** فقط تجمیع. اگر روزی کسی وسوسه شد
   «فقط اسم پایین‌ترین‌ها» را اضافه کند، همان لحظه این نما به یک دور زدنِ
   کنترل دسترسی تبدیل می‌شود — چون مدیرعامل عمداً به رکوردهای خارج از زنجیرهٔ
   خودش دسترسی ندارد.
۲. **هر میانگینِ گروهی از سرکوب کوهورت رد می‌شود** (P1-08). استثنا فقط آمارِ
   *خودِ* ارزیاب است: او همان نمره‌ها را خودش داده و چیزی کشف نمی‌کند.
"""
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import Float, func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.enums import EvaluationStatus, PersonnelStatus, UserRole
from app.models.evaluation import EvaluationRecord, EvaluationScore
from app.models.indicator import Indicator
from app.models.personnel import Personnel
from app.schemas.analytics import (
    ContractExposure,
    CycleTime,
    ExecutiveOverview,
    IndicatorGap,
    MyScoringProfile,
    RecommendationSlice,
    ScoreDistributionBucket,
    SitePerformance,
    UnitPerformance,
)
from app.schemas.auth import CurrentUser
from app.services.org_unit import site_of
from app.services.privacy import is_below_cohort, suppressed_avg
from app.services.scoring_scheme import current_rules
from app.services.workflow import IS_OPEN_RECORD

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

_FINALIZED = EvaluationRecord.status == EvaluationStatus.finalized

#: افق‌های ریسک قرارداد. سه بازه، نه یکی: «۳۰ روز» فوریت است و «۹۰ روز» برنامه‌ریزی،
#: و مدیر باید هر دو را هم‌زمان ببیند تا بفهمد آیا عقب افتاده یا فقط شلوغ است.
_EXPOSURE_HORIZONS = (30, 60, 90)


def _round(value, digits: int = 2) -> float | None:
    return round(float(value), digits) if value is not None else None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) / 2


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    index = min(len(values) - 1, int(round(fraction * (len(values) - 1))))
    return values[index]


@router.get("/my-scoring", response_model=MyScoringProfile)
def my_scoring_profile(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles(UserRole.unit_supervisor, UserRole.deputy)
    ),
) -> MyScoringProfile:
    """آینهٔ ارزیاب — نمره‌دهی خودم در برابر نمره‌دهی سازمان.

    «مالِ من» یعنی نمره‌هایی که روی پرونده‌هایی داده شده که *من* ارزیابِ مرحلهٔ
    نمره‌دهی‌شان بوده‌ام. برای معاونت این شامل مسیر «مدیر» هم می‌شود، جایی که
    خودش نقش نمره‌دهندهٔ اول را دارد (unit_supervisor_user_id خالی است).

    فقط پرونده‌های نهایی‌شده شمرده می‌شوند: نمرهٔ پیش‌نویس هنوز تصمیم نیست و
    واردکردنش، پروفایل ارزیاب را با چیزی که ممکن است هرگز ثبت نشود آلوده می‌کند.
    """
    uid = current_user.id
    if current_user.role == UserRole.deputy:
        mine = (EvaluationRecord.unit_supervisor_user_id == uid) | (
            (EvaluationRecord.unit_supervisor_user_id.is_(None))
            & (EvaluationRecord.deputy_user_id == uid)
        )
    else:
        mine = EvaluationRecord.unit_supervisor_user_id == uid

    my_scores = (
        select(EvaluationScore.score, EvaluationScore.indicator_id, EvaluationScore.evidence_text)
        .join(EvaluationRecord, EvaluationRecord.id == EvaluationScore.evaluation_record_id)
        .where(_FINALIZED, mine)
    ).subquery()
    other_scores = (
        select(
            EvaluationScore.score,
            EvaluationScore.indicator_id,
            EvaluationRecord.subject_personnel_id,
        )
        .join(EvaluationRecord, EvaluationRecord.id == EvaluationScore.evaluation_record_id)
        .where(_FINALIZED, ~mine)
    ).subquery()

    my_count = db.scalar(select(func.count()).select_from(my_scores)) or 0
    my_avg = _round(db.scalar(select(func.avg(my_scores.c.score))))

    other_count = db.scalar(select(func.count()).select_from(other_scores)) or 0
    # آستانهٔ سرکوب روی *تعداد افراد* اعمال می‌شود، نه تعداد ردیف نمره.
    #
    # این تفاوت، کل ماجراست: هر ارزیابی حدود بیست ردیف نمره دارد، پس شمردنِ ردیف‌ها
    # یعنی «میانگینِ بیست نمره‌ی یک نفر» از آستانه رد می‌شود و به‌عنوان آمار گروهی
    # نمایش داده می‌شود. آن عدد آمار گروهی نیست؛ میانگین همان یک نفر است — و به
    # ارزیابی نشان داده می‌شود که عمداً به رکورد او دسترسی ندارد.
    other_people = (
        db.scalar(select(func.count(func.distinct(other_scores.c.subject_personnel_id)))) or 0
    )
    # مقایسه با «بقیه» است نه با «همه»: اگر نمره‌های خودم داخل میانگین سازمان
    # باشند، هرچه سهم من بیشتر باشد فاصله کوچک‌تر دیده می‌شود — یعنی دقیقاً همان
    # ارزیابی که بیشترین انحراف را دارد، کمترین انحراف را می‌بیند.
    org_avg = suppressed_avg(
        _round(db.scalar(select(func.avg(other_scores.c.score)))), other_people
    )

    # --- توزیع ۱ تا ۵ -------------------------------------------------------
    my_by_score = dict(
        db.execute(
            select(my_scores.c.score, func.count()).group_by(my_scores.c.score)
        ).all()
    )
    other_by_score = dict(
        db.execute(
            select(other_scores.c.score, func.count()).group_by(other_scores.c.score)
        ).all()
    )
    distribution = [
        ScoreDistributionBucket(
            score=value,
            my_count=my_by_score.get(value, 0),
            my_share_pct=round(my_by_score.get(value, 0) * 100 / my_count, 1) if my_count else 0.0,
            # سهم توزیع هم یک آمار گروهی است: با چند نمرهٔ معدود، «۵۰٪ نمرهٔ ۲
            # داده‌اند» یعنی یک نفر یک نمرهٔ ۲ داده است.
            org_share_pct=(
                round(other_by_score.get(value, 0) * 100 / other_count, 1)
                if other_count and not is_below_cohort(other_people)
                else None
            ),
        )
        for value in range(1, 6)
    ]

    # --- فاصله روی هر شاخص --------------------------------------------------
    my_by_indicator = {
        iid: (avg, count)
        for iid, avg, count in db.execute(
            select(my_scores.c.indicator_id, func.avg(my_scores.c.score), func.count()).group_by(
                my_scores.c.indicator_id
            )
        ).all()
    }
    other_by_indicator = {
        iid: (avg, people)
        for iid, avg, people in db.execute(
            select(
                other_scores.c.indicator_id,
                func.avg(other_scores.c.score),
                # باز هم *افراد*، نه ردیف‌ها — به همان دلیلی که بالاتر توضیح داده شد
                func.count(func.distinct(other_scores.c.subject_personnel_id)),
            ).group_by(other_scores.c.indicator_id)
        ).all()
    }
    indicators = db.execute(
        select(Indicator.id, Indicator.category, Indicator.description).order_by(
            Indicator.section, Indicator.display_order
        )
    ).all()
    indicator_gaps = []
    for iid, category, description in indicators:
        my_stat = my_by_indicator.get(iid)
        if my_stat is None:
            continue  # روی این شاخص هرگز نمره نداده‌ام؛ ردیف خالی چیزی نمی‌گوید
        other_stat = other_by_indicator.get(iid)
        indicator_gaps.append(
            IndicatorGap(
                indicator_id=iid,
                category=category,
                description=description,
                my_avg=_round(my_stat[0]),
                org_avg=(
                    suppressed_avg(_round(other_stat[0]), other_stat[1])
                    if other_stat
                    else None
                ),
                my_count=my_stat[1],
            )
        )
    # بیشترین انحراف در صدر — ارزیاب باید اول جایی را ببیند که بیشتر از همه با
    # بقیه فرق دارد، نه ترتیب فرم را.
    indicator_gaps.sort(
        key=lambda g: abs((g.my_avg or 0) - g.org_avg) if g.org_avg is not None else -1,
        reverse=True,
    )

    with_evidence = (
        db.scalar(
            select(func.count()).select_from(my_scores).where(
                my_scores.c.evidence_text.is_not(None), func.trim(my_scores.c.evidence_text) != ""
            )
        )
        or 0
    )

    # --- زمانِ من در مرحلهٔ خودم -------------------------------------------
    # برای پروندهٔ نهایی‌شده، «ثبت» همان لحظه‌ای است که از draft بیرون رفت. آن لحظه
    # را نگه نمی‌داریم، ولی audit log دارد؛ به‌جای پیوند سنگین با لاگ، از تقریبِ
    # صادقانه‌تری استفاده می‌کنیم: پرونده‌های بازِ من که همین حالا روی میز من‌اند.
    open_mine = [
        row[0]
        for row in db.execute(
            select(EvaluationRecord.stage_entered_at).where(
                IS_OPEN_RECORD, mine, EvaluationRecord.status == EvaluationStatus.draft
            )
        ).all()
    ]
    now = datetime.now(UTC)
    waiting_days = sorted((now - entered).total_seconds() / 86400 for entered in open_mine)

    return MyScoringProfile(
        my_score_count=my_count,
        my_avg_score=my_avg,
        org_avg_score=org_avg,
        org_people_count=other_people,
        distribution=distribution,
        indicator_gaps=indicator_gaps,
        evidence_rate_pct=round(with_evidence * 100 / my_count, 1) if my_count else None,
        median_days_in_my_stage=_round(_median(waiting_days), 1),
        open_with_me=len(open_mine),
    )


@router.get("/executive", response_model=ExecutiveOverview)
def executive_overview(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.ceo, UserRole.deputy)),
) -> ExecutiveOverview:
    """نمای مدیریتی — فقط تجمیع، بدون هیچ نامی.

    مدیرعامل تا امروز یک صف داشت و نه یک نما: نمی‌دید کدام واحد عقب است، ترکیب
    توصیه‌ها به تمدید قرارداد چه می‌گوید، یا چرخهٔ تصمیم چقدر طول می‌کشد. این سه
    دقیقاً همان چیزهایی‌اند که بودجه و اختیار رویشان تصمیم می‌گیرد.
    """
    total = db.scalar(select(func.count()).select_from(EvaluationRecord).where(_FINALIZED)) or 0
    avg_final = suppressed_avg(
        _round(db.scalar(select(func.avg(EvaluationRecord.final_weighted_pct)).where(_FINALIZED)), 1),
        total,
    )

    unit_rows = db.execute(
        select(Personnel.org_unit, func.avg(EvaluationRecord.final_weighted_pct), func.count())
        .join(Personnel, Personnel.id == EvaluationRecord.subject_personnel_id)
        .where(_FINALIZED, EvaluationRecord.final_weighted_pct.is_not(None))
        .group_by(Personnel.org_unit)
        .order_by(func.avg(EvaluationRecord.final_weighted_pct).desc())
    ).all()
    by_org_unit = [
        UnitPerformance(
            org_unit=unit, avg_final_pct=suppressed_avg(_round(avg, 1), count), count=count
        )
        for unit, avg, count in unit_rows
    ]

    # تجمیعِ محل در پایتون و نه در SQL: قرارداد جداکننده یک تصمیم *محصولی* است
    # (توضیحش در services/org_unit.py) و بردنش داخل کوئری یعنی همان قانون در دو
    # زبان نوشته شود. تعداد واحدها ده‌ها است، نه میلیون‌ها.
    site_totals: dict[str, list[float]] = {}
    for unit, avg, count in unit_rows:
        site = site_of(unit)
        if site is None or avg is None:
            continue
        bucket = site_totals.setdefault(site, [0.0, 0.0])
        bucket[0] += float(avg) * count
        bucket[1] += count
    by_site = [
        SitePerformance(
            site=site,
            # میانگینِ وزنی بر حسب تعداد، نه میانگینِ میانگین‌ها — وگرنه واحدی با
            # دو نفر همان‌قدر وزن داشت که واحدی با پنجاه نفر.
            avg_final_pct=suppressed_avg(_round(total / count, 1), int(count)),
            count=int(count),
        )
        for site, (total, count) in sorted(
            site_totals.items(), key=lambda item: item[1][0] / item[1][1], reverse=True
        )
    ]

    recommendation_rows = db.execute(
        select(EvaluationRecord.recommendation, func.count())
        .where(_FINALIZED, EvaluationRecord.recommendation.is_not(None))
        .group_by(EvaluationRecord.recommendation)
    ).all()
    recommendation_total = sum(count for _, count in recommendation_rows)
    # ترتیب از بدترین بند به بهترین، نه از پرتکرار به کم‌تکرار: این نمودار یک
    # نردبان است و خواننده‌اش دنبال «چند نفر ته نردبان‌اند» می‌گردد.
    band_of = {
        label: index
        for index, (_, label) in enumerate(current_rules(db).thresholds)
    }
    recommendation_mix = [
        RecommendationSlice(
            recommendation=label,
            count=count,
            share_pct=round(count * 100 / recommendation_total, 1),
            band_index=band_of.get(label),
        )
        for label, count in sorted(
            recommendation_rows,
            # برچسبِ ناشناخته (از نسخهٔ قدیمی‌ترِ طرح) ته فهرست می‌رود.
            key=lambda row: (band_of.get(row[0], len(band_of)), -row[1]),
        )
    ]

    # --- زمان چرخه ----------------------------------------------------------
    durations = sorted(
        row[0]
        for row in db.execute(
            select(
                func.extract(
                    "epoch", EvaluationRecord.finalized_at - EvaluationRecord.created_at
                ).cast(Float)
                / 86400.0
            ).where(_FINALIZED, EvaluationRecord.finalized_at.is_not(None))
        ).all()
        if row[0] is not None
    )
    open_ages = sorted(
        row[0]
        for row in db.execute(
            select(
                func.extract("epoch", func.now() - EvaluationRecord.stage_entered_at).cast(Float)
                / 86400.0
            ).where(IS_OPEN_RECORD)
        ).all()
        if row[0] is not None
    )
    cycle_time = CycleTime(
        finalized_count=len(durations),
        median_days=_round(_median(durations), 1),
        p90_days=_round(_percentile(durations, 0.9), 1),
        oldest_open_stage_days=_round(open_ages[-1], 1) if open_ages else None,
        open_count=len(open_ages),
    )

    # --- ریسک تمدید --------------------------------------------------------
    contract_exposure = []
    for horizon in _EXPOSURE_HORIZONS:
        cutoff = date.today() + timedelta(days=horizon)
        expiring_where = (
            Personnel.status == PersonnelStatus.active,
            Personnel.contract_end_date.is_not(None),
            Personnel.contract_end_date <= cutoff,
        )
        expiring = db.scalar(select(func.count()).select_from(Personnel).where(*expiring_where)) or 0
        has_finalized = (
            select(EvaluationRecord.id)
            .where(EvaluationRecord.subject_personnel_id == Personnel.id, _FINALIZED)
            .exists()
        )
        uncovered = (
            db.scalar(
                select(func.count())
                .select_from(Personnel)
                .where(*expiring_where, ~has_finalized)
            )
            or 0
        )
        contract_exposure.append(
            ContractExposure(
                horizon_days=horizon, expiring=expiring, without_finalized_evaluation=uncovered
            )
        )

    return ExecutiveOverview(
        total_finalized=total,
        avg_final_pct=avg_final,
        by_org_unit=by_org_unit,
        by_site=by_site,
        recommendation_mix=recommendation_mix,
        cycle_time=cycle_time,
        contract_exposure=contract_exposure,
    )
