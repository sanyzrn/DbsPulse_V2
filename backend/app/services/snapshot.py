"""ساخت snapshot نهایی ارزیابی — سند مرجع PDF.

snapshot در لحظه تأیید نهایی ثبت می‌شود تا تغییرات بعدی (شاخص‌ها، نام‌ها و...)
سند حقوقی را عوض نکند. فیلد snapshot_version برای تحول‌پذیری شِما است: هر تغییر
شکل در آینده باید نسخه را بالا ببرد و رندر PDF بر اساس نسخه شاخه شود.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contract_self_assessment import (
    ContractSelfAssessment,
    ContractSelfAssessmentScore,
)
from app.models.evaluation import EvaluationComment, EvaluationRecord, EvaluationScore
from app.models.indicator import Indicator
from app.models.personnel import Personnel
from app.models.user import User
from app.services.self_assessment import assessment_for_evaluation
from app.services.workflow import is_direct_ceo_path, is_manager_path

# ۵: خودارزیابی مستقل از پرونده و متصل به قرارداد استخدامی است.
# ۴: افزودن `self_assessment` — برگهٔ مقایسهٔ «خود فرد / مسئول مستقیم» داخل سند.
# ۳: افزودن `single_decider` — نمره‌دهندهٔ اول و تأییدکنندهٔ نهایی یک نفر بوده‌اند.
# ۲: افزودن امتیاز ویژه (`bonus_points` / `bonus_reason` / `base_weighted_pct`).
# افزودنی است، پس قالب PDF هر دو نسخه را رندر می‌کند: در snapshot نسخهٔ ۱ این
# کلیدها نیستند و بخشِ مربوطه اصلاً چاپ نمی‌شود.
SNAPSHOT_VERSION = 5


def build_final_snapshot(db: Session, record: EvaluationRecord) -> dict:
    personnel = db.get(Personnel, record.subject_personnel_id)
    # FK تضمین می‌کند پرسنل وجود دارد، اما یک نگهبان صریح مانع 500 مبهم در صورت
    # ناسازگاری داده می‌شود و پیام روشن می‌دهد.
    if personnel is None:
        raise ValueError("پرسنل مرتبط با این ارزیابی یافت نشد؛ امکان ساخت سند نهایی نیست")
    scores = db.scalars(select(EvaluationScore).where(EvaluationScore.evaluation_record_id == record.id)).all()
    self_assessment = assessment_for_evaluation(db, record)
    self_scores = self_assessment.scores if self_assessment is not None else []
    comments = db.scalars(select(EvaluationComment).where(EvaluationComment.evaluation_record_id == record.id)).all()
    indicators_by_id = {i.id: i for i in db.scalars(select(Indicator))}

    manager_path = is_manager_path(record)
    direct_ceo_path = is_direct_ceo_path(record)
    evaluator_user_id = (
        record.ceo_user_id
        if direct_ceo_path
        else record.deputy_user_id
        if manager_path
        else record.unit_supervisor_user_id
    )
    evaluator = db.get(User, evaluator_user_id)

    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "personnel": {
            "full_name": personnel.full_name,
            "personnel_code": personnel.personnel_code,
            "job_title": personnel.job_title,
            "org_unit": personnel.org_unit,
        },
        "evaluator": {
            "username": evaluator.username if evaluator else None,
            "role_label": "مدیرعامل" if direct_ceo_path else "معاونت" if manager_path else "مسئول واحد",
        },
        # اگر نمره‌دهندهٔ اول و تأییدکنندهٔ نهایی یک نفر بوده‌اند، سند باید همین
        # را بگوید. دو تأیید در لاگ، بدون این جمله، دو بررسی مستقل به‌نظر می‌رسد.
        "single_decider": record.single_decider,
        # برگهٔ مقایسه — دیدگاه خودِ فرد کنار نمرهٔ ارزیاب، در همان سندی که
        # قطعی می‌شود. `None` یعنی خودارزیابی ثبت نشده، که کاملاً مجاز است؛
        # قالب در آن حالت اصلاً این بخش را چاپ نمی‌کند.
        #
        # عمداً در snapshot می‌نشیند و نه به‌صورت query در لحظهٔ چاپ: سند نهایی
        # باید همان چیزی را نشان بدهد که در لحظهٔ نهایی‌شدن بوده.
        "self_assessment": _self_assessment_block(self_assessment, self_scores, scores, indicators_by_id),
        "evaluation_started_at": record.created_at.isoformat(),
        "evaluation_code": record.evaluation_code,
        "general_score_pct": float(record.general_score_pct) if record.general_score_pct is not None else None,
        "specialized_score_pct": float(record.specialized_score_pct)
        if record.specialized_score_pct is not None
        else None,
        "final_weighted_pct": float(record.final_weighted_pct) if record.final_weighted_pct is not None else None,
        # امتیازِ فرم پیش از امتیاز ویژه. سند نهایی باید بتواند بگوید عدد نهایی
        # از کجا آمده — «۸۴ از فرم + ۳ بابتِ فلان کار»، نه یک ۸۷ بی‌منشأ.
        "base_weighted_pct": float(record.base_weighted_pct) if record.base_weighted_pct is not None else None,
        "bonus_points": float(record.bonus_points) if record.bonus_points else None,
        "bonus_reason": record.bonus_reason,
        "recommendation": record.recommendation,
        "evaluator_comment": record.evaluator_comment,
        # اگر شاخصی پس از امتیازدهی حذف شده باشد، snapshot نباید 500 بدهد؛ ردیف با
        # برچسب جایگزین حفظ می‌شود تا امتیاز ثبت‌شده در سند نهایی گم نشود.
        "scores": [
            {
                "indicator_id": s.indicator_id,
                "category": ind.category if (ind := indicators_by_id.get(s.indicator_id)) else "—",
                "description": ind.description if ind else "(شاخص حذف‌شده)",
                "section": ind.section.value if ind else "general",
                "score": s.score,
                "evidence_text": s.evidence_text,
            }
            for s in scores
        ],
        "comments": [
            {
                "stage": c.stage.value,
                "commenter_user_id": c.commenter_user_id,
                "comment_text": c.comment_text,
            }
            for c in comments
        ],
        "finalized_at": record.finalized_at.isoformat() if record.finalized_at else None,
    }


def _self_assessment_block(
    assessment: ContractSelfAssessment | None,
    self_scores: list[ContractSelfAssessmentScore],
    evaluator_scores: list[EvaluationScore],
    indicators_by_id: dict[int, Indicator],
) -> dict | None:
    """دیدگاه خودِ فرد، به شکلی که کنار نمرهٔ ارزیاب چاپ شود.

    ردیف‌ها بر اساس *بزرگیِ اختلاف* مرتب می‌شوند، نه شمارهٔ شاخص: جایی که فرد ۵
    داده و ارزیاب ۲، همان جایی است که خواندنش ارزش دارد. `gap` از پیش حساب
    می‌شود تا قالب هیچ محاسبه‌ای نکند.

    مبنا *خودارزیابی* است و نه نمره‌های ارزیاب: شاخصی که فرد به آن نمره داده و
    ارزیاب هنوز نداده، باید در برگه بماند — حذفش یعنی سند، حرفِ خودِ فرد را
    بی‌صدا انداخته است.
    """
    if assessment is None or assessment.submitted_at is None:
        return None

    evaluator_by_indicator = {row.indicator_id: row.score for row in evaluator_scores}
    rows = []
    for entry in self_scores:
        indicator = indicators_by_id.get(entry.indicator_id)
        evaluator_score = evaluator_by_indicator.get(entry.indicator_id)
        rows.append(
            {
                "indicator_id": entry.indicator_id,
                "category": indicator.category if indicator else "—",
                "description": indicator.description if indicator else "(شاخص حذف‌شده)",
                "self_score": entry.score,
                "evaluator_score": evaluator_score,
                "gap": None if evaluator_score is None else entry.score - evaluator_score,
                "note": entry.note,
            }
        )
    rows.sort(key=lambda row: abs(row["gap"] or 0), reverse=True)
    return {
        "submitted_at": assessment.submitted_at.isoformat(),
        "note": assessment.note,
        "rows": rows,
    }
