from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.constants import (
    EVIDENCE_EXEMPT_SCORE,
    EVIDENCE_REQUIRED_MIN_WORDS,
    GENERAL_SECTION_WEIGHT,
    SPECIALIZED_SECTION_WEIGHT,
)
from app.schemas.auth import CurrentUser
from app.schemas.common import AppConfig

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=AppConfig)
def get_config(current_user: CurrentUser = Depends(get_current_user)) -> AppConfig:
    return AppConfig(
        evidence_min_words=EVIDENCE_REQUIRED_MIN_WORDS,
        evidence_exempt_score=EVIDENCE_EXEMPT_SCORE,
        general_section_weight=GENERAL_SECTION_WEIGHT,
        specialized_section_weight=SPECIALIZED_SECTION_WEIGHT,
    )
