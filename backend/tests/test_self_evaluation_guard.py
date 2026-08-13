"""P0-10 — کسی نباید ارزیابِ خودش باشد.

خروجی این سامانه توصیه به تمدید یا عدم‌تمدید قرارداد است؛ اگر یک مدیر بتواند ارزیابِ
پروندهٔ خودش باشد، کل زنجیرهٔ تأیید بی‌معنا می‌شود. دو مسیر رسیدن به این حالت تست
می‌شوند، هم در لایهٔ API و هم در لایهٔ دیتابیس (تریگر).
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.evaluation_access import EvaluationAccess
from tests.helpers import auth_header, make_access, make_personnel, make_user


def test_hr_cannot_assign_a_personnel_their_own_user_as_evaluator(client, db_session):
    hr = make_user(db_session, "hr")
    personnel = make_personnel(db_session)
    # کاربر «معاونتِ» این پرسنل، خودِ همان پرسنل است
    himself = make_user(db_session, "deputy", personnel_id=personnel.id)
    ceo = make_user(db_session, "ceo")
    sup = make_user(db_session, "unit_supervisor")
    db_session.commit()

    r = client.put(
        f"/api/personnel/{personnel.id}/access",
        json={
            "unit_supervisor_user_id": sup.id,
            "deputy_user_id": himself.id,
            "ceo_user_id": ceo.id,
        },
        headers=auth_header(hr),
    )

    assert r.status_code == 400
    assert "ارزیابِ خودش" in r.json()["detail"]


def test_unrelated_evaluators_are_still_accepted(client, db_session):
    hr = make_user(db_session, "hr")
    personnel = make_personnel(db_session)
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    db_session.commit()

    r = client.put(
        f"/api/personnel/{personnel.id}/access",
        json={
            "unit_supervisor_user_id": sup.id,
            "deputy_user_id": dep.id,
            "ceo_user_id": ceo.id,
        },
        headers=auth_header(hr),
    )

    assert r.status_code == 200


def test_hr_cannot_link_an_existing_evaluator_to_the_personnel_they_evaluate(client, db_session):
    hr = make_user(db_session, "hr")
    personnel = make_personnel(db_session)
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    # دسترسی درست است؛ حالا HR می‌خواهد کاربرِ معاونت را به همان پرسنل لینک کند.
    r = client.patch(
        f"/api/users/{dep.id}",
        json={"personnel_id": personnel.id},
        headers=auth_header(hr),
    )

    assert r.status_code == 400
    assert "ارزیابِ این پرسنل" in r.json()["detail"]


def test_linking_a_user_to_an_unrelated_personnel_is_fine(client, db_session):
    hr = make_user(db_session, "hr")
    personnel = make_personnel(db_session)
    other_personnel = make_personnel(db_session)
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    r = client.patch(
        f"/api/users/{dep.id}",
        json={"personnel_id": other_personnel.id},
        headers=auth_header(hr),
    )

    assert r.status_code == 200


def test_database_trigger_rejects_self_evaluating_access_written_directly(db_session):
    """پشتیبان سطح دیتابیس: حتی INSERT مستقیم — بدون عبور از API — هم رد می‌شود."""
    personnel = make_personnel(db_session)
    himself = make_user(db_session, "deputy", personnel_id=personnel.id)
    ceo = make_user(db_session, "ceo")
    db_session.flush()

    db_session.add(
        EvaluationAccess(
            personnel_id=personnel.id,
            unit_supervisor_user_id=None,
            deputy_user_id=himself.id,
            ceo_user_id=ceo.id,
        )
    )
    with pytest.raises(IntegrityError, match="self-evaluation is not allowed"):
        db_session.flush()


def test_database_trigger_rejects_linking_an_evaluator_directly(db_session):
    personnel = make_personnel(db_session)
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.flush()

    dep.personnel_id = personnel.id
    with pytest.raises(IntegrityError, match="self-evaluation is not allowed"):
        db_session.flush()
