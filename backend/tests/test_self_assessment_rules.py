"""Contract-owned self-assessment behavior."""

from datetime import date, timedelta

from app.models.contract_self_assessment import ContractSelfAssessment
from tests.helpers import (
    active_indicators,
    auth_header,
    make_access,
    make_personnel,
    make_user,
)


def _employee(db_session, *, role: str = "employee", **personnel_overrides):
    personnel = make_personnel(db_session, **personnel_overrides)
    user = make_user(db_session, role, personnel_id=personnel.id)
    db_session.commit()
    return personnel, user


def _payload(db_session, score: int = 4):
    return {
        "scores": [
            {"indicator_id": indicator.id, "score": score, "note": None} for indicator in active_indicators(db_session)
        ],
        "note": "دستاوردهای قرارداد جاری",
    }


def test_form_is_open_without_an_evaluation_case(client, db_session):
    personnel, employee = _employee(db_session)

    response = client.get("/api/me/self-assessment/current", headers=auth_header(employee))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["personnel_id"] == personnel.id
    assert body["open"] is True
    assert body["state"] == "pending"
    assert body["indicator_ids"]


def test_submission_is_once_per_contract_and_extension_does_not_reopen_it(client, db_session):
    personnel, employee = _employee(db_session)
    first = client.post(
        "/api/me/self-assessment",
        json=_payload(db_session),
        headers=auth_header(employee),
    )
    assert first.status_code == 200, first.text

    personnel.contract_end_date += timedelta(days=90)
    db_session.commit()
    second = client.post(
        "/api/me/self-assessment",
        json=_payload(db_session, 1),
        headers=auth_header(employee),
    )

    assert second.status_code == 400
    assert "قبلاً ثبت شده" in second.json()["detail"]
    rows = db_session.query(ContractSelfAssessment).filter_by(personnel_id=personnel.id).all()
    assert len(rows) == 1


def test_a_new_contract_start_date_allows_one_new_submission(client, db_session):
    personnel, employee = _employee(db_session)
    first = client.post(
        "/api/me/self-assessment",
        json=_payload(db_session),
        headers=auth_header(employee),
    )
    assert first.status_code == 200, first.text

    personnel.contract_start_date = date.today()
    personnel.contract_end_date = date.today() + timedelta(days=365)
    db_session.commit()
    current = client.get("/api/me/self-assessment/current", headers=auth_header(employee))
    assert current.status_code == 200
    assert current.json()["open"] is True
    assert current.json()["submitted_at"] is None

    second = client.post(
        "/api/me/self-assessment",
        json=_payload(db_session, 3),
        headers=auth_header(employee),
    )
    assert second.status_code == 200, second.text
    assert db_session.query(ContractSelfAssessment).filter_by(personnel_id=personnel.id).count() == 2


def test_form_is_closed_outside_the_active_contract(client, db_session):
    _, employee = _employee(
        db_session,
        contract_start_date=date.today() - timedelta(days=365),
        contract_end_date=date.today() - timedelta(days=1),
    )
    current = client.get("/api/me/self-assessment/current", headers=auth_header(employee))
    assert current.status_code == 200
    assert current.json()["open"] is False
    assert current.json()["state"] == "closed"

    submitted = client.post(
        "/api/me/self-assessment",
        json=_payload(db_session),
        headers=auth_header(employee),
    )
    assert submitted.status_code == 400
    assert "قرارداد فعال" in submitted.json()["detail"]


def test_supervisor_is_eligible_but_deputy_is_not(client, db_session):
    _, supervisor = _employee(db_session, role="unit_supervisor")
    _, deputy = _employee(db_session, role="deputy")

    supervisor_view = client.get("/api/me/self-assessment/current", headers=auth_header(supervisor))
    deputy_view = client.get("/api/me/self-assessment/current", headers=auth_header(deputy))

    assert supervisor_view.json()["open"] is True
    assert deputy_view.json()["eligible"] is False
    assert deputy_view.json()["state"] == "not_eligible"


def test_hr_view_uses_the_selected_person_not_the_hr_employees_own_personnel(client, db_session):
    hr_personnel = make_personnel(db_session, full_name="کارمند منابع انسانی")
    hr = make_user(db_session, "hr", personnel_id=hr_personnel.id)
    subject, employee = _employee(db_session, full_name="کارمند انتخاب‌شده")
    submitted = client.post(
        "/api/me/self-assessment",
        json=_payload(db_session, 5),
        headers=auth_header(employee),
    )
    assert submitted.status_code == 200, submitted.text

    viewed = client.get(
        f"/api/personnel/{subject.id}/self-assessment",
        headers=auth_header(hr),
    )

    assert viewed.status_code == 200, viewed.text
    assert viewed.json()["personnel_id"] == subject.id
    assert viewed.json()["personnel_name"] == "کارمند انتخاب‌شده"
    assert viewed.json()["scores"][0]["score"] == 5


def test_hr_can_invite_without_an_evaluation_case(client, db_session):
    hr = make_user(db_session, "hr")
    personnel, employee = _employee(db_session)

    response = client.post(
        f"/api/personnel/{personnel.id}/invite-self-assessment",
        headers=auth_header(hr),
    )

    assert response.status_code == 200, response.text
    assert response.json()["self_assessment_state"] == "invited"
    notifications = client.get("/api/notifications", headers=auth_header(employee)).json()
    rows = notifications["items"] if isinstance(notifications, dict) else notifications
    assert any(row["type"] == "self_assessment_invited" for row in rows)


def test_evaluation_opened_after_self_assessment_uses_the_same_framework(client, db_session):
    personnel, employee = _employee(db_session)
    supervisor = make_user(db_session, "unit_supervisor")
    deputy = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    make_access(db_session, personnel, supervisor, deputy, ceo)
    submitted = client.post(
        "/api/me/self-assessment",
        json=_payload(db_session),
        headers=auth_header(employee),
    )
    assert submitted.status_code == 200

    evaluation = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": personnel.id},
        headers=auth_header(supervisor),
    )
    assert evaluation.status_code == 201, evaluation.text

    detail = client.get(f"/api/evaluations/{evaluation.json()['id']}", headers=auth_header(make_user(db_session, "hr")))
    assert detail.status_code == 200, detail.text
    assert detail.json()["self_assessment"] is not None
    assert len(detail.json()["self_assessment"]["scores"]) == len(active_indicators(db_session))
