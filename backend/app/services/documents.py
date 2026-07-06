import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.evaluation import EvaluationRecord
from app.models.evaluation_document import EvaluationDocument
from app.services.pdf import render_evaluation_summary_pdf, weasyprint_available

logger = logging.getLogger(__name__)


def verify_url_for(evaluation_code: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/verify/{evaluation_code}"


def get_document(db: Session, record_id: int) -> EvaluationDocument | None:
    return db.scalar(
        select(EvaluationDocument).where(
            EvaluationDocument.evaluation_record_id == record_id
        )
    )


def archive_final_pdf(db: Session, record: EvaluationRecord) -> EvaluationDocument | None:
    """PDF نهایی را یک‌بار تولید، هش و ذخیره می‌کند (idempotent: اگر از قبل باشد
    همان را برمی‌گرداند). QR تأیید اصالت داخل سند تعبیه می‌شود.

    اگر WeasyPrint در دسترس نباشد (کتابخانه‌های بومی GTK/GObject نصب نیستند)،
    با یک warning برمی‌گردد تا ارزیابی بدون مشکل نهایی شود — PDF بعداً
    از طریق نقشه مسیر /summary.pdf قابل تولید خواهد بود.
    """
    existing = get_document(db, record.id)
    if existing is not None:
        return existing

    if not weasyprint_available():
        logger.warning(
            "Skipping PDF archival for evaluation %s: WeasyPrint native libraries "
            "are not installed. The evaluation will still be finalized successfully.",
            record.evaluation_code,
        )
        return None

    try:
        pdf_bytes = render_evaluation_summary_pdf(
            record.final_snapshot, verify_url=verify_url_for(record.evaluation_code)
        )
    except RuntimeError:
        logger.warning(
            "PDF generation failed for evaluation %s; skipping archival. "
            "The evaluation will still be finalized.",
            record.evaluation_code,
            exc_info=True,
        )
        return None

    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    document = EvaluationDocument(
        evaluation_record_id=record.id, pdf_bytes=pdf_bytes, sha256=sha256
    )
    db.add(document)
    db.flush()
    return document
