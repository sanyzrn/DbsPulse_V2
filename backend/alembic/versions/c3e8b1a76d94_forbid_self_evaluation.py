"""forbid self evaluation

P0-10 — هیچ کاربری نباید ارزیابِ پرسنلی باشد که خودش به آن متصل است.

گاردهای کد در app/services/self_evaluation.py هستند و پیام خطای تمیز می‌دهند؛ این‌جا
پشتیبانِ سطح دیتابیس است تا مسیرهای دیگر (SQL دستی روی پروداکشن، اسکریپت import، یا
endpoint آینده‌ای که یادش برود) هم نتوانند این حالت را بسازند.

CHECK constraint معمولی این کار را نمی‌کند: شرط به جدول `users` ارجاع می‌دهد و
Postgres در CHECK اجازهٔ ارجاع بین‌جدولی نمی‌دهد. پس تریگر.

Revision ID: c3e8b1a76d94
Revises: a1d7f4e9b602
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3e8b1a76d94'
down_revision: Union[str, None] = 'a1d7f4e9b602'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# نام ستونِ «سوژه» بین دو جدول فرق دارد، پس از TG_ARGV می‌خوانیمش و یک تابع مشترک
# برای هر دو تریگر کافی است.
_SUBJECT_SIDE_FUNCTION = """
CREATE OR REPLACE FUNCTION forbid_self_evaluation() RETURNS trigger AS $$
DECLARE
    subject_id integer := (to_jsonb(NEW) ->> TG_ARGV[0])::integer;
    conflicting text;
BEGIN
    IF subject_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT string_agg(u.username, ', ')
      INTO conflicting
      FROM users u
     WHERE u.personnel_id = subject_id
       AND u.id IN (NEW.unit_supervisor_user_id, NEW.deputy_user_id, NEW.ceo_user_id);

    IF conflicting IS NOT NULL THEN
        RAISE EXCEPTION
            'self-evaluation is not allowed: user(s) % are linked to personnel #%',
            conflicting, subject_id
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

# سمت دیگر همان نامساوی: کاربر از قبل ارزیاب است و حالا به همان پرسنل لینک می‌شود.
_USER_SIDE_FUNCTION = """
CREATE OR REPLACE FUNCTION forbid_self_evaluation_on_user_link() RETURNS trigger AS $$
BEGIN
    IF NEW.personnel_id IS NULL THEN
        RETURN NEW;
    END IF;

    IF EXISTS (
        SELECT 1 FROM evaluation_access a
         WHERE a.personnel_id = NEW.personnel_id
           AND NEW.id IN (a.unit_supervisor_user_id, a.deputy_user_id, a.ceo_user_id)
    ) OR EXISTS (
        SELECT 1 FROM evaluation_records r
         WHERE r.subject_personnel_id = NEW.personnel_id
           AND NEW.id IN (r.unit_supervisor_user_id, r.deputy_user_id, r.ceo_user_id)
    ) THEN
        RAISE EXCEPTION
            'self-evaluation is not allowed: user #% is an evaluator of personnel #%',
            NEW.id, NEW.personnel_id
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(_SUBJECT_SIDE_FUNCTION)
    op.execute(_USER_SIDE_FUNCTION)

    op.execute(
        "CREATE TRIGGER trg_evaluation_access_no_self_evaluation "
        "BEFORE INSERT OR UPDATE ON evaluation_access "
        "FOR EACH ROW EXECUTE FUNCTION forbid_self_evaluation('personnel_id')"
    )
    op.execute(
        "CREATE TRIGGER trg_evaluation_records_no_self_evaluation "
        "BEFORE INSERT OR UPDATE ON evaluation_records "
        "FOR EACH ROW EXECUTE FUNCTION forbid_self_evaluation('subject_personnel_id')"
    )
    op.execute(
        "CREATE TRIGGER trg_users_no_self_evaluation "
        "BEFORE INSERT OR UPDATE OF personnel_id ON users "
        "FOR EACH ROW EXECUTE FUNCTION forbid_self_evaluation_on_user_link()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_users_no_self_evaluation ON users")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_evaluation_records_no_self_evaluation ON evaluation_records"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_evaluation_access_no_self_evaluation ON evaluation_access"
    )
    op.execute("DROP FUNCTION IF EXISTS forbid_self_evaluation_on_user_link()")
    op.execute("DROP FUNCTION IF EXISTS forbid_self_evaluation()")
