"""قواعد نمره‌دهیِ جاری، برای فرم امتیازدهی در فرانت‌اند.

از طرح *فعال* خوانده می‌شود، نه از ثابت‌ها (P1-04). بدون این، HR می‌توانست
حداقل کلمات شواهد را عوض کند و فرم همچنان قاعدهٔ قدیمی را اعتبارسنجی کند —
یعنی کاربر تیک سبز می‌گرفت و بعد سرور ثبت را رد می‌کرد.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.text_limits import BONUS_REASON_MIN
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.common import AppConfig
from app.services.scoring_scheme import current_rules

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=AppConfig)
def get_config(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AppConfig:
    rules = current_rules(db)
    return AppConfig(
        evidence_min_words=rules.evidence_min_words,
        evidence_max_words=rules.evidence_max_words,
        evidence_required_scores=list(rules.evidence_required_scores),
        general_section_weight=rules.general_section_weight,
        specialized_section_weight=rules.specialized_section_weight,
        bonus_max_points=rules.bonus_max_points,
        bonus_reason_min_length=BONUS_REASON_MIN,
    )
