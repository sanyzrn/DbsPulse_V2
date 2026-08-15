"""seed sample users personnel access

Revision ID: 1eaa459f4dde
Revises: 74797edbc85f
Create Date: 2026-07-01 04:05:58.591955

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

from app.core.config import settings
from app.core.demo_data import DEMO_PASSWORD
from app.core.security import hash_password

# revision identifiers, used by Alembic.
revision: str = '1eaa459f4dde'
down_revision: Union[str, None] = '74797edbc85f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # این کاربران یک رمز مشترک دارند که در مخزن عمومی منتشر شده است. پیش‌تر این
    # مایگریشن بی‌قید و شرط اجرا می‌شد، یعنی هر محیطی که مایگریشن می‌خورد —
    # از جمله production — پنج اعتبارنامهٔ معتبر و عمومی پیدا می‌کرد (hr1 عملاً
    # super-admin است). حالا فقط با SEED_DEMO_DATA=true ساخته می‌شوند.
    if not settings.seed_demo_data:
        return

    conn = op.get_bind()

    def insert_user(username: str, role: str) -> int:
        return conn.execute(
            text(
                "INSERT INTO users (username, password_hash, role, is_active) "
                "VALUES (:username, :password_hash, :role, true) RETURNING id"
            ),
            {"username": username, "password_hash": hash_password(DEMO_PASSWORD), "role": role},
        ).scalar_one()

    hr_id = insert_user("hr1", "hr")
    sup1_id = insert_user("sup1", "unit_supervisor")
    sup2_id = insert_user("sup2", "unit_supervisor")
    deputy_id = insert_user("dep1", "deputy")
    ceo_id = insert_user("ceo1", "ceo")

    def insert_personnel(code: str, full_name: str, job_title: str, org_unit: str) -> int:
        return conn.execute(
            text(
                "INSERT INTO personnel "
                "(personnel_code, full_name, job_title, org_unit, contract_start_date, "
                " contract_end_date, status, created_by_user_id) "
                "VALUES (:code, :full_name, :job_title, :org_unit, '2025-01-01', '2026-12-31', "
                " 'active', :created_by) RETURNING id"
            ),
            {
                "code": code,
                "full_name": full_name,
                "job_title": job_title,
                "org_unit": org_unit,
                "created_by": hr_id,
            },
        ).scalar_one()

    p_sales_id = insert_personnel("P-1001", "علی محمدی", "کارشناس فروش", "فروش")
    p_it_id = insert_personnel("P-1002", "زهرا کریمی", "کارشناس فناوری اطلاعات", "فناوری اطلاعات")
    p_manager_id = insert_personnel("P-1003", "حسین رضایی", "مدیر", "فروش")

    def insert_access(personnel_id: int, supervisor_id: int | None) -> None:
        conn.execute(
            text(
                "INSERT INTO evaluation_access "
                "(personnel_id, unit_supervisor_user_id, deputy_user_id, ceo_user_id, updated_by_user_id) "
                "VALUES (:personnel_id, :supervisor_id, :deputy_id, :ceo_id, :hr_id)"
            ),
            {
                "personnel_id": personnel_id,
                "supervisor_id": supervisor_id,
                "deputy_id": deputy_id,
                "ceo_id": ceo_id,
                "hr_id": hr_id,
            },
        )

    insert_access(p_sales_id, sup1_id)
    insert_access(p_it_id, sup2_id)
    insert_access(p_manager_id, None)  # عنوان شغلی «مدیر»: دسترسی مسئول واحد ندارد


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DELETE FROM evaluation_access WHERE personnel_id IN (SELECT id FROM personnel WHERE personnel_code IN ('P-1001','P-1002','P-1003'))"))
    conn.execute(text("DELETE FROM personnel WHERE personnel_code IN ('P-1001','P-1002','P-1003')"))
    conn.execute(text("DELETE FROM users WHERE username IN ('hr1','sup1','sup2','dep1','ceo1')"))
