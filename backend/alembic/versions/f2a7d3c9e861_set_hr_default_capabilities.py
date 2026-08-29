"""Set the baseline capabilities for human-resources accounts.

Revision ID: f2a7d3c9e861
Revises: e4b90d7c2f18
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text


revision: str = "f2a7d3c9e861"
down_revision: str | Sequence[str] | None = "e4b90d7c2f18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        text(
            """
            DELETE FROM user_capabilities
            WHERE user_id IN (SELECT id FROM users WHERE role = 'hr')
              AND capability NOT IN (
                  'manage_users', 'manage_personnel', 'manage_scoring'
              )
            """
        )
    )
    for capability in ("manage_users", "manage_personnel", "manage_scoring"):
        connection.execute(
            text(
                """
                INSERT INTO user_capabilities (user_id, capability)
                SELECT id, :capability
                FROM users
                WHERE role = 'hr'
                ON CONFLICT (user_id, capability) DO NOTHING
                """
            ),
            {"capability": capability},
        )


def downgrade() -> None:
    # Revoking elevated permissions is deliberately irreversible: their former
    # values cannot be reconstructed safely.
    pass
