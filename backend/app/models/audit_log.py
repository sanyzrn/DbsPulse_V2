from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("evaluation_records.id"), nullable=True
    )
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # زنجیرهٔ تمپر-اویدنت (P1-09): هر ردیف هشِ محتوای خودش را نگه می‌دارد، به‌علاوهٔ
    # هشِ ردیف قبلی. دست‌بردن در یک ردیفِ میانی همهٔ حلقه‌های بعدی را می‌شکند، پس
    # ویرایشِ نامرئی یعنی بازمحاسبهٔ کل دنبالهٔ بعد از آن.
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
