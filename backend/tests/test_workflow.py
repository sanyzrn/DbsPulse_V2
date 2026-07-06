from tests.helpers import active_indicators, auth_header, full_valid_scores, make_access, make_personnel, make_user


def _score_payload(indicators, evidence_indicator_id, score=4):
    scores = full_valid_scores(indicators)
    for row in scores:
        if row["indicator_id"] == evidence_indicator_id:
            row["score"] = score
            row["evidence_text"] = " ".join(["کلمه"] * 16)
    return scores


def test_regular_evaluation_full_workflow(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session, job_title="کارشناس")
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    indicators = active_indicators(db_session)
    assert len(indicators) == 20

    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    )
    assert r.status_code == 201, r.text
    evaluation = r.json()
    assert evaluation["status"] == "draft"
    assert evaluation["stage"] == "supervisor_scoring"

    scores = _score_payload(indicators, indicators[0].id)
    r = client.put(
        f"/api/evaluations/{evaluation['id']}/scores", json={"scores": scores}, headers=auth_header(sup)
    )
    assert r.status_code == 200, r.text

    r = client.post(f"/api/evaluations/{evaluation['id']}/submit", headers=auth_header(sup))
    assert r.status_code == 200, r.text
    evaluation = r.json()
    assert evaluation["status"] == "submitted"
    assert evaluation["final_weighted_pct"] is not None

    # deputy cannot approve while still in HR review
    r = client.post(f"/api/evaluations/{evaluation['id']}/deputy-approve", headers=auth_header(dep))
    assert r.status_code == 403

    r = client.post(f"/api/evaluations/{evaluation['id']}/hr-approve", headers=auth_header(hr))
    assert r.status_code == 200
    assert r.json()["status"] == "hr_approved"

    # deputy cannot edit scores on the regular path
    r = client.put(
        f"/api/evaluations/{evaluation['id']}/scores", json={"scores": scores}, headers=auth_header(dep)
    )
    assert r.status_code == 403

    r = client.post(
        f"/api/evaluations/{evaluation['id']}/comments",
        json={"comment_text": "نظر معاونت"},
        headers=auth_header(dep),
    )
    assert r.status_code == 201

    r = client.post(f"/api/evaluations/{evaluation['id']}/deputy-approve", headers=auth_header(dep))
    assert r.status_code == 200
    assert r.json()["status"] == "deputy_approved"

    r = client.post(f"/api/evaluations/{evaluation['id']}/ceo-finalize", headers=auth_header(ceo))
    assert r.status_code == 200
    final = r.json()
    assert final["status"] == "finalized"
    assert final["finalized_at"] is not None

    r = client.get(f"/api/evaluations/{evaluation['id']}", headers=auth_header(hr))
    detail = r.json()
    assert len(detail["scores"]) == 20
    assert len(detail["comments"]) == 1

    r = client.get(f"/api/evaluations/{evaluation['id']}/summary.pdf", headers=auth_header(hr))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_manager_job_title_skips_supervisor_stage(client, db_session):
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    sup = make_user(db_session, "unit_supervisor")
    manager = make_personnel(db_session, job_title="مدیر", is_manager=True)
    make_access(db_session, manager, None, dep, ceo)
    db_session.commit()

    # a regular unit_supervisor must not be able to start this evaluation
    r = client.post("/api/evaluations", json={"subject_personnel_id": manager.id}, headers=auth_header(sup))
    assert r.status_code == 403

    r = client.post("/api/evaluations", json={"subject_personnel_id": manager.id}, headers=auth_header(dep))
    assert r.status_code == 201, r.text
    evaluation = r.json()
    assert evaluation["status"] == "hr_approved"
    assert evaluation["stage"] == "deputy_review"
    assert evaluation["unit_supervisor_user_id"] is None

    indicators = active_indicators(db_session)
    scores = _score_payload(indicators, indicators[0].id)

    # a regular supervisor must not be able to score a manager-path evaluation
    r = client.put(
        f"/api/evaluations/{evaluation['id']}/scores", json={"scores": scores}, headers=auth_header(sup)
    )
    assert r.status_code == 403

    r = client.put(
        f"/api/evaluations/{evaluation['id']}/scores", json={"scores": scores}, headers=auth_header(dep)
    )
    assert r.status_code == 200, r.text

    r = client.post(f"/api/evaluations/{evaluation['id']}/deputy-approve", headers=auth_header(dep))
    assert r.status_code == 200, r.text
    evaluation = r.json()
    assert evaluation["status"] == "deputy_approved"
    assert evaluation["stage"] == "ceo_final"
    assert evaluation["final_weighted_pct"] is not None

    r = client.post(f"/api/evaluations/{evaluation['id']}/ceo-finalize", headers=auth_header(ceo))
    assert r.status_code == 200
    assert r.json()["status"] == "finalized"


def test_submit_rejects_incomplete_evidence(client, db_session):
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    r = client.post("/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup))
    evaluation_id = r.json()["id"]

    indicators = active_indicators(db_session)
    scores = full_valid_scores(indicators)
    # give the first indicator a non-3 score with insufficient evidence
    scores[0]["score"] = 5
    scores[0]["evidence_text"] = "کلمه کلمه"

    client.put(f"/api/evaluations/{evaluation_id}/scores", json={"scores": scores}, headers=auth_header(sup))
    r = client.post(f"/api/evaluations/{evaluation_id}/submit", headers=auth_header(sup))
    assert r.status_code == 400
    assert "حداقل ۱۵ کلمه" in r.json()["detail"]


def test_submit_rejects_incomplete_indicator_coverage(client, db_session):
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    r = client.post("/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup))
    evaluation_id = r.json()["id"]

    indicators = active_indicators(db_session)
    scores = full_valid_scores(indicators)[:-1]  # یک شاخص را جا می‌اندازیم
    client.put(f"/api/evaluations/{evaluation_id}/scores", json={"scores": scores}, headers=auth_header(sup))
    r = client.post(f"/api/evaluations/{evaluation_id}/submit", headers=auth_header(sup))
    assert r.status_code == 400
    assert "تمام شاخص" in r.json()["detail"]


def test_second_open_evaluation_for_same_personnel_is_rejected_with_409(client, db_session):
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    r = client.post("/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup))
    assert r.status_code == 201
    first_id = r.json()["id"]

    # تلاش دوم (مثلاً دابل‌کلیک) باید ۴۰۹ برگرداند و به پرونده باز موجود اشاره کند
    r = client.post("/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup))
    assert r.status_code == 409
    assert r.json()["detail"]["evaluation_id"] == first_id


def test_new_evaluation_allowed_after_previous_is_finalized(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    indicators = active_indicators(db_session)
    r = client.post("/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup))
    evaluation_id = r.json()["id"]
    client.put(
        f"/api/evaluations/{evaluation_id}/scores",
        json={"scores": full_valid_scores(indicators)},
        headers=auth_header(sup),
    )
    assert client.post(f"/api/evaluations/{evaluation_id}/submit", headers=auth_header(sup)).status_code == 200
    assert client.post(f"/api/evaluations/{evaluation_id}/hr-approve", headers=auth_header(hr)).status_code == 200
    assert client.post(f"/api/evaluations/{evaluation_id}/deputy-approve", headers=auth_header(dep)).status_code == 200
    assert client.post(f"/api/evaluations/{evaluation_id}/ceo-finalize", headers=auth_header(ceo)).status_code == 200

    # پس از نهایی‌شدن، شروع ارزیابی جدید برای همان پرسنل آزاد است
    r = client.post("/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup))
    assert r.status_code == 201
