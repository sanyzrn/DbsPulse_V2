from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EvaluationAccess(Base):
    __tablename__ = "evaluation_access"

    id: Mapped[int] = mapped_column(primary_key=True)
    personnel_id: Mapped[int] = mapped_column(ForeignKey("personnel.id"), nullable=False)
    unit_supervisor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deputy_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    ceo_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
