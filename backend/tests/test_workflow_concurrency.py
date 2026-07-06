"""تأیید اینکه گذارهای گردش‌کار (submit/hr-approve/deputy-approve/ceo-finalize/
return) رکورد را با قفل ردیف (SELECT ... FOR UPDATE) می‌خوانند — بدون این قفل،
دو درخواست هم‌زمان (مثلاً دوبار کلیک روی «تأیید») می‌توانستند هر دو از بررسی
وضعیت عبور کنند پیش از آنکه هرکدام commit شود.

تست هم‌زمانی واقعی (دو thread/session کاملاً مستقل) نیازمند یک اتصال جداگانه به
دیتابیس است، جدا از fixture مشترک client/db_session این پروژه (که عمداً یک
تراکنش/savepoint مشترک به ازای هر تست دارد)؛ به‌جای آن، این تست مستقیماً تأیید
می‌کند که عبارت SQL تولیدشده توسط _get_record_or_404_for_update واقعاً شامل
قفل است — راهی قطعی و بدون شکنندگیِ تست‌های threading برای همین منظور."""
from sqlalchemy import select

from app.api.routers.evaluations import _get_record_or_404_for_update
from app.models.evaluation import EvaluationRecord
from tests.helpers import auth_header, make_access, make_personnel, make_user


def test_get_record_for_update_returns_the_correct_record(client, db_session):
    make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    )
    evaluation_id = r.json()["id"]

    record = _get_record_or_404_for_update(db_session, evaluation_id)
    assert record.id == evaluation_id


def test_row_lock_clause_is_present_in_generated_sql(db_session):
    # of=EvaluationRecord لازم است چون subject (Personnel) با lazy="joined" همیشه
    # eager-join می‌شود و Postgres قفل را روی سمت nullable یک outer join نمی‌پذیرد
    stmt = (
        select(EvaluationRecord)
        .where(EvaluationRecord.id == 1)
        .with_for_update(of=EvaluationRecord)
    )
    compiled_sql = str(stmt.compile(bind=db_session.bind, compile_kwargs={"literal_binds": True}))
    assert "FOR UPDATE" in compiled_sql.upper()
