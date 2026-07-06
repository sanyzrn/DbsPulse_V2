from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EvaluationDocument(Base):
    """PDF نهاییِ آرشیوشده به‌همراه هش SHA-256 آن.

    سند در لحظه تأیید نهایی یک‌بار تولید و ذخیره می‌شود؛ از آن پس همان بایت‌ها
    سرو می‌شوند تا تغییرات بعدی قالب/داده، سندِ حقوقیِ صادرشده را عوض نکند.
    هش برای تأیید اصالت نسخه چاپی (از طریق QR) استفاده می‌شود.
    """

    __tablename__ = "evaluation_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_record_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_records.id"), unique=True, nullable=False
    )
    pdf_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
