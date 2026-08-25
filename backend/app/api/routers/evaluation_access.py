from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role_or_capability
from app.db.session import get_db
from app.models.enums import Capability, UserRole
from app.models.evaluation_access import EvaluationAccess
from app.models.personnel import Personnel
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.schemas.evaluation_access import EvaluationAccessRead, EvaluationAccessUpsert
from app.services.audit import log_event
from app.services.self_evaluation import (
    ensure_chain_stages_are_not_redundant,
    ensure_evaluators_are_not_the_subject,
)
from app.services.workflow import may_act_at

router = APIRouter(prefix="/api/personnel/{personnel_id}/access", tags=["evaluation-access"])

_ROLE_LABELS = {
    UserRole.unit_supervisor: "مسئول واحد",
    UserRole.deputy: "معاونت",
    UserRole.ceo: "مدیرعامل",
}


def _ensure_active_user_with_role(db: Session, user_id: int, expected_role: UserRole) -> None:
    """کاربر ارجاع‌شده باید موجود، فعال و با نقش درست باشد؛ در غیر این صورت پرونده‌های
    ارزیابی با تأییدکننده‌ای ساخته می‌شوند که هرگز نمی‌تواند اقدام کند (پرونده گیر می‌کند)."""
    label = _ROLE_LABELS[expected_role]
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"کاربر انتخاب‌شده برای «{label}» یافت نشد یا غیرفعال است",
        )
    # مافوق می‌تواند در مرحلهٔ پایین‌تر بنشیند: مدیرعاملی که برای چند نفر خودش
    # مسئول مستقیم است، یا معاونتی که نمره‌دهندهٔ اول است. با سنجشِ نقشِ دقیق،
    # چنین آدمی اصلاً قابل انتخاب نبود.
    if not may_act_at(user.role, expected_role):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"کاربر انتخاب‌شده برای «{label}» نمی‌تواند در این مرحله قرار بگیرد",
        )


@router.get("", response_model=EvaluationAccessRead | None)
def get_access(
    personnel_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role_or_capability(UserRole.hr, Capability.manage_personnel)),
) -> EvaluationAccess | None:
    # پرسنل ناموجود باید 404 بگیرد (نه 200 با بدنهٔ null) تا با upsert_access یکسان
    # باشد و تایپوی شناسه پنهان نماند.
    if db.get(Personnel, personnel_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    return db.scalar(select(EvaluationAccess).where(EvaluationAccess.personnel_id == personnel_id))


@router.put("", response_model=EvaluationAccessRead)
def upsert_access(
    personnel_id: int,
    payload: EvaluationAccessUpsert,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role_or_capability(UserRole.hr, Capability.manage_personnel)),
) -> EvaluationAccess:
    personnel = db.get(Personnel, personnel_id)
    if personnel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")

    if personnel.is_manager and payload.unit_supervisor_user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                'چون این فرد به‌عنوان «مدیر» علامت خورده است، نمی‌توان دسترسی مسئول واحد را برای او '
                "فعال کرد؛ این فرد مستقیماً توسط معاونت ارزیابی می‌شود."
            ),
        )

    if payload.unit_supervisor_user_id is None and payload.deputy_user_id is None:
        # اگر هر دو مرحلهٔ میانی خالی باشند، هیچ‌کس نمره نمی‌دهد و پرونده از همان
        # اول در حالتی می‌ماند که فقط لغو از آن خارجش می‌کند.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دست‌کم یکی از «مسئول واحد» یا «معاونت» باید تعیین شود؛ وگرنه نمره‌دهنده‌ای وجود ندارد",
        )
    if payload.unit_supervisor_user_id is not None:
        _ensure_active_user_with_role(db, payload.unit_supervisor_user_id, UserRole.unit_supervisor)
    if payload.deputy_user_id is not None:
        _ensure_active_user_with_role(db, payload.deputy_user_id, UserRole.deputy)
    _ensure_active_user_with_role(db, payload.ceo_user_id, UserRole.ceo)
    ensure_evaluators_are_not_the_subject(
        db,
        personnel_id,
        [payload.unit_supervisor_user_id, payload.deputy_user_id, payload.ceo_user_id],
    )
    ensure_chain_stages_are_not_redundant(
        db,
        payload.unit_supervisor_user_id,
        payload.deputy_user_id,
        payload.ceo_user_id,
    )

    access = db.scalar(select(EvaluationAccess).where(EvaluationAccess.personnel_id == personnel_id))
    if access is None:
        access = EvaluationAccess(personnel_id=personnel_id)
        db.add(access)
        old_value = None
    else:
        old_value = {
            "unit_supervisor_user_id": access.unit_supervisor_user_id,
            "deputy_user_id": access.deputy_user_id,
            "ceo_user_id": access.ceo_user_id,
        }

    access.unit_supervisor_user_id = payload.unit_supervisor_user_id
    access.deputy_user_id = payload.deputy_user_id
    access.ceo_user_id = payload.ceo_user_id
    access.updated_by_user_id = current_user.id

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="access_updated",
        old_value=old_value,
        new_value={
            "personnel_id": personnel_id,
            "unit_supervisor_user_id": payload.unit_supervisor_user_id,
            "deputy_user_id": payload.deputy_user_id,
            "ceo_user_id": payload.ceo_user_id,
        },
    )
    db.commit()
    db.refresh(access)
    return access
