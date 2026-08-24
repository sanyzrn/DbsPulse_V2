import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.metrics import pdf_renders
from app.models.evaluation import EvaluationRecord
from app.models.evaluation_document import EvaluationDocument
from app.services.pdf import render_evaluation_summary_pdf, weasyprint_available

logger = logging.getLogger(__name__)


def verify_url_for(verify_token: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/verify/{verify_token}"


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
        pdf_renders.labels(outcome="skipped_no_weasyprint").inc()
        logger.warning(
            "Skipping PDF archival for evaluation %s: WeasyPrint native libraries "
            "are not installed. The evaluation will still be finalized successfully.",
            record.evaluation_code,
        )
        return None

    # رکوردهای نهایی‌شده (چه از این پس، چه backfill شدهٔ migration) همیشه verify_token
    # دارند؛ اگر به هر دلیلی نداشت (رکورد خیلی قدیمی که هرگز backfill نشده)، لینک تأیید
    # را نمی‌سازیم تا evaluation_code ترتیبی هرگز روی endpoint عمومی افشا نشود.
    verify_url = verify_url_for(record.verify_token) if record.verify_token else None
    try:
        pdf_bytes = render_evaluation_summary_pdf(record.final_snapshot, verify_url=verify_url)
    except RuntimeError:
        pdf_renders.labels(outcome="failed").inc()
        logger.warning(
            "PDF generation failed for evaluation %s; skipping archival. "
            "The evaluation will still be finalized.",
            record.evaluation_code,
            exc_info=True,
        )
        return None

    pdf_renders.labels(outcome="succeeded").inc()
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    document = EvaluationDocument(
        evaluation_record_id=record.id, pdf_bytes=pdf_bytes, sha256=sha256
    )
    # بررسیِ «از قبل هست؟» در بالای تابع در برابر هم‌زمانی کافی نیست، و پنجره‌اش
    # هم تئوریک نیست: پس از نهایی‌سازی، ساخت سند در پس‌زمینه شروع می‌شود و رندر
    # WeasyPrint چند ثانیه طول می‌کشد. هر دانلودی که در همان چند ثانیه برسد،
    # «نیست» می‌بیند، خودش رندر می‌کند و موقع درج به قید یکتا می‌خورد — یعنی
    # کاربر دقیقاً در لحظه‌ای که تازه خبر نهایی‌شدن را گرفته، خطای ۵۰۰ می‌گیرد.
    #
    # SAVEPOINT لازم است: بدون آن، خطای درج کل تراکنشِ درخواست را می‌سوزاند و
    # حتی خواندنِ ردیفِ موجود هم دیگر ممکن نیست.
    try:
        with db.begin_nested():
            db.add(document)
    except IntegrityError:
        # شیء در حال درج، با برگشتِ SAVEPOINT خودش از session بیرون رفته است.
        # طرف مقابل commit کرده (وگرنه درج ما منتظر می‌ماند، نه اینکه خطا بدهد)،
        # پس همان سند حالا خواندنی است. دو رندرِ هم‌زمانِ یک snapshot یکی‌اند.
        return get_document(db, record.id)
    return document


def archive_final_pdf_detached(record_id: int) -> None:
    """همان کار، ولی در یک session مستقل — برای اجرای پس از ارسال پاسخ (P2-05).

    WeasyPrint یک کتابخانهٔ بومیِ سنگین است و تا امروز *داخل* درخواستِ نهایی‌سازی
    مدیرعامل اجرا می‌شد: یعنی کندشدن رندر، به شکستِ مهم‌ترین اقدام سامانه ترجمه
    می‌شد. حالا پرونده اول نهایی و commit می‌شود، بعد سند ساخته می‌شود.

    session خودش را می‌سازد چون session درخواست، هنگام اجرای این تابع بسته شده
    است. خطاها بلعیده می‌شوند و فقط لاگ می‌گیرند: این کار پس‌زمینه است و شکستش
    نباید هیچ اثری روی پروندهٔ نهایی‌شده بگذارد — جاروی زمان‌بند
    (run_document_backfill_sweep) بعداً دوباره تلاش می‌کند.
    """
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        record = db.get(EvaluationRecord, record_id)
        if record is None:
            return
        archive_final_pdf(db, record)
        db.commit()
    except Exception:  # noqa: BLE001 — کار پس‌زمینه نباید هیچ‌چیزی را بشکند
        db.rollback()
        logger.warning("Background PDF archival failed for record %s", record_id, exc_info=True)
    finally:
        db.close()
