"""ویرایشگر طرح نمره‌دهی برای منابع انسانی (P1-04).

تا امروز وزن‌ها و آستانه‌ها ثابت‌های پایتون بودند: مشتری‌ای که ۷۰/۳۰ می‌خواست به
یک تغییر کد و بیلد و استقرار نیاز داشت. حالا HR می‌تواند طرح تازه بسازد، اثرش را
روی پرونده‌های واقعی *ببیند*، و بعد فعالش کند.

دو گارد که این قابلیت را از یک تفنگِ پرشده جدا می‌کنند:

**۱. پیش‌نمایش روی دادهٔ واقعی.** «۰٫۷ به‌جای ۰٫۶» یک عدد است و پیامدش قابل تصور
نیست؛ «۱۴ نفر از تمدید استاندارد به تمدید مشروط منتقل می‌شوند» یک تصمیم است.
پیش‌نمایش دقیقاً همان `compute_result` واقعی را اجرا می‌کند، نه یک کپیِ موازی که
دیر یا زود با اصل فرق می‌کند.

**۲. فعال‌سازی دو نفره.** کسی که طرح را ساخته نمی‌تواند خودش فعالش کند. تغییر
قاعدهٔ نمره‌دهیِ کل سازمان — چیزی که مستقیماً به تصمیم تمدید قرارداد ترجمه
می‌شود — نباید تصمیم یک نفرِ تنها باشد. همان منطقی که پشت جداسازی وظایف در
بقیهٔ زنجیره است.

و یک قاعدهٔ سخت: **طرح فعال‌شده تغییرناپذیر است.** برای عوض کردن هر عددی باید
نسخهٔ تازه ساخت. ویرایش درجای یک نسخهٔ فعال یعنی بازنویسیِ بی‌صدای معنای هر
پروندهٔ گذشته.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_capability
from app.db.session import get_db
from app.models.enums import Capability, EvaluationStatus, SchemeStatus
from app.models.evaluation import EvaluationRecord, EvaluationScore
from app.models.indicator import Indicator
from app.models.personnel import Personnel
from app.models.scoring_scheme import ScoringScheme
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.schemas.scoring_scheme import (
    ReclassifiedCase,
    SchemeInput,
    SchemePreview,
    SchemeRead,
)
from app.services.audit import log_event
from app.services.evaluation import compute_result
from app.services.scoring_scheme import Rules, activate, next_version

router = APIRouter(prefix="/api/scoring-schemes", tags=["scoring-schemes"])

#: چند پروندهٔ نهایی‌شدهٔ اخیر در پیش‌نمایش سنجیده می‌شود. سقف لازم است چون این
#: کار همهٔ نمره‌های آن پرونده‌ها را می‌خواند و دوباره حساب می‌کند.
PREVIEW_LIMIT = 200


def _rules_from_input(payload: SchemeInput) -> Rules:
    return Rules(
        general_section_weight=payload.general_section_weight,
        specialized_section_weight=payload.specialized_section_weight,
        evidence_required_scores=tuple(payload.evidence_required_scores),
        evidence_min_words=payload.evidence_min_words,
        evidence_max_words=payload.evidence_max_words,
        thresholds=tuple((b.upper_exclusive, b.label) for b in payload.thresholds),
        indicator_weights=dict(payload.indicator_weights),
        bonus_max_points=payload.bonus_max_points,
        improvement_plan_max_pct=payload.improvement_plan_max_pct,
    )


def _to_read(db: Session, scheme: ScoringScheme) -> SchemeRead:
    creator = db.get(User, scheme.created_by_user_id) if scheme.created_by_user_id else None
    activator = db.get(User, scheme.activated_by_user_id) if scheme.activated_by_user_id else None
    return SchemeRead(
        id=scheme.id,
        version=scheme.version,
        name=scheme.name,
        status=scheme.status,
        general_section_weight=float(scheme.general_section_weight),
        specialized_section_weight=float(scheme.specialized_section_weight),
        evidence_required_scores=[int(s) for s in scheme.evidence_required_scores],
        evidence_min_words=scheme.evidence_min_words,
        evidence_max_words=scheme.evidence_max_words,
        bonus_max_points=float(scheme.bonus_max_points),
        improvement_plan_max_pct=float(scheme.improvement_plan_max_pct),
        thresholds=scheme.thresholds,
        indicator_weights={int(k): float(v) for k, v in (scheme.indicator_weights or {}).items()},
        created_at=scheme.created_at,
        created_by_username=creator.username if creator else None,
        activated_at=scheme.activated_at,
        activated_by_username=activator.username if activator else None,
        retired_at=scheme.retired_at,
    )


@router.get("", response_model=list[SchemeRead])
def list_schemes(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_scoring)),
) -> list[SchemeRead]:
    """همهٔ نسخه‌ها، تازه‌ترین اول — تاریخچهٔ قواعدِ سازمان."""
    schemes = db.scalars(select(ScoringScheme).order_by(ScoringScheme.version.desc())).all()
    return [_to_read(db, scheme) for scheme in schemes]


@router.post("", response_model=SchemeRead, status_code=status.HTTP_201_CREATED)
def create_scheme(
    payload: SchemeInput,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_scoring)),
) -> SchemeRead:
    """یک پیش‌نویس تازه. تا فعال نشده هیچ اثری روی هیچ پرونده‌ای ندارد."""
    scheme = ScoringScheme(
        version=next_version(db),
        name=payload.name,
        status=SchemeStatus.draft,
        general_section_weight=payload.general_section_weight,
        specialized_section_weight=payload.specialized_section_weight,
        evidence_required_scores=payload.evidence_required_scores,
        evidence_min_words=payload.evidence_min_words,
        evidence_max_words=payload.evidence_max_words,
        bonus_max_points=payload.bonus_max_points,
        improvement_plan_max_pct=payload.improvement_plan_max_pct,
        thresholds=[b.model_dump() for b in payload.thresholds],
        # کلیدهای JSONB باید رشته باشند
        indicator_weights={str(k): v for k, v in payload.indicator_weights.items()},
        created_by_user_id=current_user.id,
    )
    db.add(scheme)
    db.flush()
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="scoring_scheme_drafted",
        new_value={"version": scheme.version, "name": scheme.name},
    )
    db.commit()
    db.refresh(scheme)
    return _to_read(db, scheme)


@router.post("/preview", response_model=SchemePreview)
def preview_scheme(
    payload: SchemeInput,
    limit: int = Query(default=PREVIEW_LIMIT, ge=1, le=PREVIEW_LIMIT),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_scoring)),
) -> SchemePreview:
    """طرح پیشنهادی را روی پرونده‌های نهایی‌شدهٔ اخیر اجرا می‌کند — بدون نوشتن.

    این محاسبه‌ای فرضی است: هیچ رکوردی عوض نمی‌شود. هدفش این است که HR *پیش از*
    فعال‌سازی ببیند تصمیمی که می‌گیرد چند نفر را از یک برچسب به برچسب دیگر
    می‌برد.
    """
    rules = _rules_from_input(payload)
    indicators_by_id = {i.id: i for i in db.scalars(select(Indicator))}

    records = db.scalars(
        select(EvaluationRecord)
        .where(
            EvaluationRecord.status == EvaluationStatus.finalized,
            EvaluationRecord.final_weighted_pct.is_not(None),
        )
        .order_by(EvaluationRecord.finalized_at.desc())
        .limit(limit)
    ).all()

    cases: list[ReclassifiedCase] = []
    transitions: dict[tuple[str, str], int] = {}
    for record in records:
        scores = [
            {"indicator_id": row.indicator_id, "score": row.score, "evidence_text": row.evidence_text}
            for row in db.scalars(
                select(EvaluationScore).where(
                    EvaluationScore.evaluation_record_id == record.id
                )
            )
        ]
        # پرونده‌ای که شاخصی از فرمِ فعلی ندارد (شاخص حذف شده) از پیش‌نمایش کنار
        # می‌رود؛ محاسبهٔ ناقص بدتر از نبودِ ردیف است.
        if not scores or any(row["indicator_id"] not in indicators_by_id for row in scores):
            continue

        # امتیاز ویژهٔ همان پرونده هم وارد محاسبهٔ فرضی می‌شود، وگرنه ستون
        # «الان» و ستون «با طرح پیشنهادی» دو چیز متفاوت را می‌سنجند و
        # جابه‌جایی‌هایی گزارش می‌شود که هیچ‌وقت اتفاق نمی‌افتند.
        proposed = compute_result(
            scores, indicators_by_id, rules, bonus_points=float(record.bonus_points or 0)
        )
        personnel = db.get(Personnel, record.subject_personnel_id)
        current_recommendation = record.recommendation or "—"
        case = ReclassifiedCase(
            evaluation_code=record.evaluation_code,
            org_unit=personnel.org_unit if personnel else "—",
            current_final_pct=float(record.final_weighted_pct),
            proposed_final_pct=proposed["final_weighted_pct"],
            current_recommendation=current_recommendation,
            proposed_recommendation=proposed["recommendation"],
        )
        cases.append(case)
        if case.changed:
            key = (current_recommendation, proposed["recommendation"])
            transitions[key] = transitions.get(key, 0) + 1

    return SchemePreview(
        sample_size=len(cases),
        changed_count=sum(1 for case in cases if case.changed),
        transitions=[
            {"from": source, "to": target, "count": count}
            for (source, target), count in sorted(
                transitions.items(), key=lambda item: item[1], reverse=True
            )
        ],
        # فقط پرونده‌هایی که برچسبشان عوض می‌شود برگردانده می‌شوند: در فهرست
        # دویست‌تایی، ردیف‌های بی‌تغییر همان چیزی را پنهان می‌کنند که باید دیده شود.
        cases=[case for case in cases if case.changed],
    )


@router.post("/{scheme_id}/activate", response_model=SchemeRead)
def activate_scheme(
    scheme_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_scoring)),
) -> SchemeRead:
    """پیش‌نویس را فعال می‌کند و نسخهٔ فعلی را بازنشسته.

    پرونده‌های موجود دست‌نخورده می‌مانند — هرکدام به نسخهٔ خودش مهر خورده و با
    همان حساب می‌شود. فقط پرونده‌های *جدید* زیر این نسخه ساخته می‌شوند.
    """
    scheme = db.get(ScoringScheme, scheme_id)
    if scheme is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="طرح یافت نشد")
    if scheme.status is not SchemeStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="فقط پیش‌نویس را می‌توان فعال کرد؛ نسخهٔ فعال یا بازنشسته تغییرناپذیر است",
        )
    # جداسازی وظایف: سازندهٔ طرح نمی‌تواند فعالش کند. تغییر قاعدهٔ نمره‌دهیِ کل
    # سازمان نباید تصمیم یک نفرِ تنها باشد.
    if scheme.created_by_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "فعال‌سازی طرح باید توسط کاربر دیگری از منابع انسانی انجام شود؛ "
                "سازندهٔ طرح نمی‌تواند خودش آن را فعال کند"
            ),
        )

    previous = db.scalar(
        select(ScoringScheme).where(ScoringScheme.status == SchemeStatus.active)
    )
    activate(db, scheme, actor_user_id=current_user.id)
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="scoring_scheme_activated",
        old_value={"version": previous.version} if previous else None,
        new_value={
            "version": scheme.version,
            "name": scheme.name,
            "drafted_by_user_id": scheme.created_by_user_id,
        },
    )
    db.commit()
    db.refresh(scheme)
    return _to_read(db, scheme)


@router.delete("/{scheme_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(
    scheme_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_scoring)),
) -> None:
    """حذف یک پیش‌نویس. فقط پیش‌نویس — نسخهٔ فعال یا بازنشسته سند تاریخ است."""
    scheme = db.get(ScoringScheme, scheme_id)
    if scheme is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="طرح یافت نشد")
    if scheme.status is not SchemeStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "نسخهٔ فعال یا بازنشسته حذف نمی‌شود: پرونده‌های موجود به آن مهر خورده‌اند "
                "و بدون آن دیگر نمی‌شود گفت با چه قواعدی حساب شده‌اند"
            ),
        )
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="scoring_scheme_draft_deleted",
        old_value={"version": scheme.version, "name": scheme.name},
    )
    db.delete(scheme)
    db.commit()
