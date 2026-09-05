from app.models.enums import Capability, EvaluationStatus
from app.models.evaluation import EvaluationRecord
from app.models.evaluation_access import EvaluationAccess
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_personnel,
    make_user,
)


def test_hr_finalizes_a_direct_ceo_case_without_returning_it_to_ceo(
    client, db_session, monkeypatch
):
    hr = make_user(db_session, "hr")
    ceo = make_user(db_session, "ceo", capabilities=[])
    personnel = make_personnel(db_session, full_name="Direct CEO report")
    db_session.add(
        EvaluationAccess(
            personnel_id=personnel.id,
            unit_supervisor_user_id=None,
            deputy_user_id=None,
            ceo_user_id=ceo.id,
        )
    )
    db_session.commit()

    created = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": personnel.id},
        headers=auth_header(ceo),
    )
    assert created.status_code == 201, created.text
    evaluation_id = created.json()["id"]

    scores = full_valid_scores(active_indicators(db_session))
    scored = client.put(
        f"/api/evaluations/{evaluation_id}/scores",
        json={"scores": scores},
        headers=auth_header(ceo),
    )
    assert scored.status_code == 200, scored.text

    submitted = client.post(
        f"/api/evaluations/{evaluation_id}/submit", headers=auth_header(ceo)
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == EvaluationStatus.submitted.value

    monkeypatch.setattr(
        "app.api.routers.evaluations.archive_final_pdf_detached", lambda _record_id: None
    )
    finalized = client.post(
        f"/api/evaluations/{evaluation_id}/hr-approve", headers=auth_header(hr)
    )
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["status"] == EvaluationStatus.finalized.value
    assert finalized.json()["single_decider"] is False

    record = db_session.get(EvaluationRecord, evaluation_id)
    db_session.refresh(record)
    assert record.hr_user_id == hr.id
    assert record.finalized_at is not None
    assert record.final_snapshot is not None
    assert record.verify_token is not None

    second_ceo_approval = client.post(
        f"/api/evaluations/{evaluation_id}/ceo-finalize", headers=auth_header(ceo)
    )
    assert second_ceo_approval.status_code == 403


def test_manage_personnel_capability_can_see_the_full_personnel_list(client, db_session):
    support = make_user(
        db_session,
        "support",
        capabilities=[Capability.manage_personnel],
    )
    personnel = make_personnel(db_session, full_name="Visible to personnel admin")
    db_session.commit()

    response = client.get("/api/personnel?limit=1000", headers=auth_header(support))
    assert response.status_code == 200, response.text
    assert any(row["id"] == personnel.id for row in response.json()["items"])
