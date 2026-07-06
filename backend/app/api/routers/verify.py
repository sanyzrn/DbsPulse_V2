from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.enums import EvaluationStatus
from app.models.evaluation import EvaluationRecord
from app.schemas.verify import VerificationResult
from app.services.documents import get_document

router = APIRouter(prefix="/api/verify", tags=["verify"])


@router.get("/{token}", response_model=VerificationResult)
@limiter.limit("30/minute")
def verify_document(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
) -> VerificationResult:
    """تأیید اصالت عمومی سند از روی توکن تصادفی (بدون احراز هویت؛ برای اسکن QR نسخه
    چاپی). عمداً از evaluation_code (ترتیبی و قابل‌شمارش: EVL-0001, EVL-0002, ...)
    به‌عنوان کلید جست‌وجو استفاده نمی‌شود — وگرنه هرکسی با شمارش کد می‌توانست نام/
    واحد/نتیجهٔ همهٔ پرسنل را استخراج کند. فقط ارزیابی‌های نهایی‌شده قابل تأییدند و
    فقط داده‌های غیرحساس برگردانده می‌شود."""
    record = db.scalar(select(EvaluationRecord).where(EvaluationRecord.verify_token == token))
    if record is None or record.status != EvaluationStatus.finalized:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سند نهایی‌شده‌ای با این کد یافت نشد",
        )

    document = get_document(db, record.id)
    snapshot = record.final_snapshot or {}
    personnel = snapshot.get("personnel", {})

    return VerificationResult(
        valid=True,
        evaluation_code=record.evaluation_code,
        subject_full_name=personnel.get("full_name", ""),
        org_unit=personnel.get("org_unit", ""),
        final_weighted_pct=float(record.final_weighted_pct)
        if record.final_weighted_pct is not None
        else None,
        recommendation=record.recommendation,
        finalized_at=record.finalized_at,
        sha256=document.sha256 if document else "",
    )
