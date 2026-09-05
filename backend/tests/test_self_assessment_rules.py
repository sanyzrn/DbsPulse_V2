"""Contract-owned self-assessment behavior."""

from datetime import date, timedelta

import pytest

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


def test_open_form_follows_admin_replacement_and_submits_latest_version(client, db_session):
    from app.services.indicator_framework import current_framework

    personnel, employee = _employee(db_session)
    hr = make_user(db_session, "hr")
    before = client.get("/api/me/self-assessment/current", headers=auth_header(employee)).json()
    old_id = before["indicator_ids"][0]
    replacement = client.post(
        f"/api/indicators/{old_id}/replace",
        json={"category": "Updated category", "description": "Updated question", "reason": "Revision"},
        headers=auth_header(hr),
    )
    assert replacement.status_code == 201, replacement.text
    new_id = replacement.json()["id"]
    after = client.get("/api/me/self-assessment/current", headers=auth_header(employee)).json()
    assert after["assessment_id"] == before["assessment_id"]
    assert old_id not in after["indicator_ids"]
    assert new_id in after["indicator_ids"]

    stale = client.post(
        "/api/me/self-assessment",
        json={"scores": [{"indicator_id": i, "score": 4} for i in before["indicator_ids"]]},
        headers=auth_header(employee),
    )
    assert stale.status_code == 400
    db_session.rollback()
    saved = client.post("/api/me/self-assessment", json=_payload(db_session), headers=auth_header(employee))
    assert saved.status_code == 200, saved.text
    assessment = db_session.get(ContractSelfAssessment, after["assessment_id"])
    assert assessment.indicator_framework_id == current_framework(db_session).id
    assert {row.indicator_id for row in assessment.scores} == set(after["indicator_ids"])


def test_submitted_self_assessment_keeps_questions_and_answers_after_admin_change(client, db_session):
    _, employee = _employee(db_session)
    hr = make_user(db_session, "hr")
    saved = client.post("/api/me/self-assessment", json=_payload(db_session), headers=auth_header(employee))
    assert saved.status_code == 200, saved.text
    before = saved.json()
    old_id = before["indicator_ids"][0]
    response = client.post(
        f"/api/indicators/{old_id}/replace",
        json={"category": "New category", "description": "New question", "reason": "Revision"},
        headers=auth_header(hr),
    )
    assert response.status_code == 201, response.text
    after = client.get("/api/me/self-assessment/current", headers=auth_header(employee)).json()
    assert after["indicator_ids"] == before["indicator_ids"]
    assert after["scores"] == before["scores"]
    assert after["submitted_at"] == before["submitted_at"]


def test_invited_form_follows_added_and_deactivated_indicators(client, db_session):
    personnel, employee = _employee(db_session)
    hr = make_user(db_session, "hr")
    invited = client.post(f"/api/personnel/{personnel.id}/invite-self-assessment", headers=auth_header(hr))
    assert invited.status_code == 200, invited.text
    old_id = active_indicators(db_session)[0].id
    disabled = client.patch(f"/api/indicators/{old_id}", json={"is_active": False}, headers=auth_header(hr))
    assert disabled.status_code == 200, disabled.text
    created = client.post(
        "/api/indicators",
        json={"section": "specialized", "category": "New skill", "description": "New question", "display_order": 99},
        headers=auth_header(hr),
    )
    assert created.status_code == 201, created.text
    current = client.get("/api/me/self-assessment/current", headers=auth_header(employee)).json()
    assert current["state"] == "invited"
    assert old_id not in current["indicator_ids"]
    assert created.json()["id"] in current["indicator_ids"]


def test_form_is_open_without_an_evaluation_case(client, db_session):
    personnel, employee = _employee(db_session)

    response = client.get("/api/me/self-assessment/current", headers=auth_header(employee))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["personnel_id"] == personnel.id
    assert body["open"] is True
    assert body["state"] == "pending"
    assert body["indicator_ids"]


@pytest.mark.parametrize("role", ["hr", "unit_supervisor"])
def test_linking_existing_account_enables_own_form_and_name_edit_preserves_link(client, db_session, role):
    personnel = make_personnel(db_session)
    user = make_user(db_session, role)
    hr = user if role == "hr" else make_user(db_session, "hr")
    db_session.commit()
    headers = auth_header(user)
    assert client.get("/api/me/self-assessment/current", headers=headers).status_code == 403

    linked = client.patch(f"/api/users/{user.id}", json={"personnel_id": personnel.id}, headers=auth_header(hr))
    assert linked.status_code == 200, linked.text
    # The existing token sees the new link without logging out or changing roles.
    current = client.get("/api/me/self-assessment/current", headers=headers)
    assert current.status_code == 200, current.text
    assert current.json()["personnel_id"] == personnel.id
    renamed = client.patch(f"/api/users/{user.id}", json={"full_name": "Updated name"}, headers=auth_header(hr))
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["personnel_id"] == personnel.id
    assert client.get("/api/me/self-assessment/current", headers=headers).status_code == 200


def test_support_can_save_unchanged_own_role_but_cannot_change_it(client, db_session):
    user = make_user(db_session, "support", capabilities=["manage_users"])
    db_session.commit()
    response = client.patch(
        f"/api/users/{user.id}", json={"role": "support", "full_name": "Administrator"}, headers=auth_header(user)
    )
    assert response.status_code == 200, response.text
    changed = client.patch(f"/api/users/{user.id}", json={"role": "hr"}, headers=auth_header(user))
    assert changed.status_code == 400


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
