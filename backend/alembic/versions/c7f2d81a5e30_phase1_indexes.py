"""phase1 indexes

ایندکس روی تمام کلیدهای خارجی/ستون‌های پرکاربرد در کوئری‌ها (تا این‌جا فقط PK و
سه unique وجود داشت و همه این کوئری‌ها sequential scan بودند) + یکتایی
(evaluation_record_id, indicator_id) روی امتیازها تا هر شاخص در هر ارزیابی
حداکثر یک ردیف امتیاز داشته باشد.

Revision ID: c7f2d81a5e30
Revises: b41c07a9d2e1
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7f2d81a5e30'
down_revision: Union[str, None] = 'b41c07a9d2e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = [
    ("ix_evaluation_scores_record", "evaluation_scores", ["evaluation_record_id"]),
    ("ix_evaluation_comments_record", "evaluation_comments", ["evaluation_record_id"]),
    ("ix_evaluation_records_subject", "evaluation_records", ["subject_personnel_id"]),
    ("ix_evaluation_records_status_created", "evaluation_records", ["status", "created_at"]),
    ("ix_evaluation_records_supervisor", "evaluation_records", ["unit_supervisor_user_id"]),
    ("ix_evaluation_records_deputy", "evaluation_records", ["deputy_user_id"]),
    ("ix_evaluation_records_ceo", "evaluation_records", ["ceo_user_id"]),
    ("ix_audit_log_created_at", "audit_log", ["created_at"]),
    ("ix_audit_log_event_type", "audit_log", ["event_type"]),
    ("ix_audit_log_record", "audit_log", ["evaluation_record_id"]),
]


def upgrade() -> None:
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)

    op.create_unique_constraint(
        "uq_evaluation_scores_record_indicator",
        "evaluation_scores",
        ["evaluation_record_id", "indicator_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_evaluation_scores_record_indicator", "evaluation_scores", type_="unique"
    )
    for name, table, _ in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
