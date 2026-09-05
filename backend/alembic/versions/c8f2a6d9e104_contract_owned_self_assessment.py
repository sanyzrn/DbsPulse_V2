"""Make self-assessment independent from evaluation creation.

Revision ID: c8f2a6d9e104
Revises: b3e9d1f47a52
Create Date: 2026-09-01

The migration is additive: legacy evaluation-owned columns and scores remain in
place, while all existing submissions are copied into the contract-owned tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c8f2a6d9e104"
down_revision: str | None = "b3e9d1f47a52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evaluation_records",
        sa.Column("subject_contract_start_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "evaluation_records",
        sa.Column("subject_contract_end_date", sa.Date(), nullable=True),
    )
    op.execute(
        """
        UPDATE evaluation_records AS er
        SET subject_contract_start_date = p.contract_start_date,
            subject_contract_end_date = p.contract_end_date
        FROM personnel AS p
        WHERE p.id = er.subject_personnel_id
        """
    )

    op.create_table(
        "contract_self_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("personnel_id", sa.Integer(), nullable=False),
        sa.Column("contract_start_date", sa.Date(), nullable=False),
        sa.Column("contract_end_date", sa.Date(), nullable=False),
        sa.Column("indicator_framework_id", sa.Integer(), nullable=False),
        sa.Column("submitted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("source_evaluation_record_id", sa.Integer(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(length=2000), nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invited_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["personnel_id"], ["personnel.id"]),
        sa.ForeignKeyConstraint(["indicator_framework_id"], ["indicator_frameworks.id"]),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_evaluation_record_id"], ["evaluation_records.id"]),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"]),
        sa.UniqueConstraint(
            "personnel_id",
            "contract_start_date",
            name="uq_contract_self_assessment_personnel_contract",
        ),
        sa.UniqueConstraint(
            "source_evaluation_record_id",
            name="uq_contract_self_assessment_source_evaluation",
        ),
    )
    op.create_index(
        "ix_contract_self_assessments_personnel",
        "contract_self_assessments",
        ["personnel_id"],
    )

    op.create_table(
        "contract_self_assessment_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contract_self_assessment_id", sa.Integer(), nullable=False),
        sa.Column("indicator_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "score BETWEEN 1 AND 5",
            name="ck_contract_self_assessment_scores_range",
        ),
        sa.ForeignKeyConstraint(
            ["contract_self_assessment_id"],
            ["contract_self_assessments.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["indicator_id"], ["indicators.id"]),
        sa.UniqueConstraint(
            "contract_self_assessment_id",
            "indicator_id",
            name="uq_contract_self_assessment_score_indicator",
        ),
    )
    op.create_index(
        "ix_contract_self_assessment_scores_assessment",
        "contract_self_assessment_scores",
        ["contract_self_assessment_id"],
    )

    op.execute(
        """
        WITH legacy AS (
            SELECT DISTINCT ON (
                er.subject_personnel_id,
                er.subject_contract_start_date
            )
                er.*
            FROM evaluation_records AS er
            WHERE er.self_assessment_submitted_at IS NOT NULL
               OR er.self_assessment_invited_at IS NOT NULL
            ORDER BY
                er.subject_personnel_id,
                er.subject_contract_start_date,
                er.self_assessment_submitted_at DESC NULLS LAST,
                er.self_assessment_invited_at DESC NULLS LAST,
                er.id DESC
        )
        INSERT INTO contract_self_assessments (
            personnel_id,
            contract_start_date,
            contract_end_date,
            indicator_framework_id,
            submitted_by_user_id,
            source_evaluation_record_id,
            submitted_at,
            note,
            invited_at,
            invited_by_user_id,
            created_at
        )
        SELECT
            legacy.subject_personnel_id,
            legacy.subject_contract_start_date,
            legacy.subject_contract_end_date,
            COALESCE(
                legacy.indicator_framework_id,
                (SELECT id FROM indicator_frameworks ORDER BY version DESC LIMIT 1)
            ),
            (
                SELECT al.actor_user_id
                FROM audit_log AS al
                WHERE al.evaluation_record_id = legacy.id
                  AND al.event_type = 'self_assessment_submitted'
                ORDER BY al.created_at DESC
                LIMIT 1
            ),
            legacy.id,
            legacy.self_assessment_submitted_at,
            legacy.self_assessment_note,
            legacy.self_assessment_invited_at,
            legacy.self_assessment_invited_by_user_id,
            COALESCE(
                legacy.self_assessment_submitted_at,
                legacy.self_assessment_invited_at,
                legacy.created_at
            )
        FROM legacy
        """
    )
    op.execute(
        """
        INSERT INTO contract_self_assessment_scores (
            contract_self_assessment_id,
            indicator_id,
            score,
            note,
            created_at
        )
        SELECT csa.id, sas.indicator_id, sas.score, sas.note, sas.created_at
        FROM self_assessment_scores AS sas
        JOIN contract_self_assessments AS csa
          ON csa.source_evaluation_record_id = sas.evaluation_record_id
        ON CONFLICT (contract_self_assessment_id, indicator_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_contract_self_assessment_scores_assessment",
        table_name="contract_self_assessment_scores",
    )
    op.drop_table("contract_self_assessment_scores")
    op.drop_index(
        "ix_contract_self_assessments_personnel",
        table_name="contract_self_assessments",
    )
    op.drop_table("contract_self_assessments")
    op.drop_column("evaluation_records", "subject_contract_end_date")
    op.drop_column("evaluation_records", "subject_contract_start_date")
