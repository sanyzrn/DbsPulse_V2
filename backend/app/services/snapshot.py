"""ساخت snapshot نهایی ارزیابی — سند مرجع PDF.

snapshot در لحظه تأیید نهایی ثبت می‌شود تا تغییرات بعدی (شاخص‌ها، نام‌ها و...)
سند حقوقی را عوض نکند. فیلد snapshot_version برای تحول‌پذیری شِما است: هر تغییر
شکل در آینده باید نسخه را بالا ببرد و رندر PDF بر اساس نسخه شاخه شود.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evaluation import EvaluationComment, EvaluationRecord, EvaluationScore
from app.models.indicator import Indicator
from app.models.personnel import Personnel
from app.models.user import User
from app.services.workflow import is_manager_path

SNAPSHOT_VERSION = 1


def build_final_snapshot(db: Session, record: EvaluationRecord) -> dict:
    personnel = db.get(Personnel, record.subject_personnel_id)
    # FK تضمین می‌کند پرسنل وجود دارد، اما یک نگهبان صریح مانع 500 مبهم در صورت
    # ناسازگاری داده می‌شود و پیام روشن می‌دهد.
    if personnel is None:
        raise ValueError("پرسنل مرتبط با این ارزیابی یافت نشد؛ امکان ساخت سند نهایی نیست")
    scores = db.scalars(
        select(EvaluationScore).where(EvaluationScore.evaluation_record_id == record.id)
    ).all()
    comments = db.scalars(
        select(EvaluationComment).where(EvaluationComment.evaluation_record_id == record.id)
    ).all()
    indicators_by_id = {i.id: i for i in db.scalars(select(Indicator))}

    manager_path = is_manager_path(record)
    evaluator_user_id = record.deputy_user_id if manager_path else record.unit_supervisor_user_id
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
            "role_label": "معاونت" if manager_path else "مسئول واحد",
        },
        "evaluation_started_at": record.created_at.isoformat(),
        "evaluation_code": record.evaluation_code,
        "general_score_pct": float(record.general_score_pct)
        if record.general_score_pct is not None
        else None,
        "specialized_score_pct": float(record.specialized_score_pct)
        if record.specialized_score_pct is not None
        else None,
        "final_weighted_pct": float(record.final_weighted_pct)
        if record.final_weighted_pct is not None
        else None,
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
