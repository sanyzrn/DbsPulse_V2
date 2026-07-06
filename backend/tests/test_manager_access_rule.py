from tests.helpers import auth_header, make_access, make_personnel, make_user


def test_manager_job_title_rejects_unit_supervisor(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    manager = make_personnel(db_session, job_title="مدیر", is_manager=True)
    db_session.commit()

    resp = client.put(
        f"/api/personnel/{manager.id}/access",
        json={
            "unit_supervisor_user_id": sup.id,
            "deputy_user_id": dep.id,
            "ceo_user_id": ceo.id,
        },
        headers=auth_header(hr),
    )
    assert resp.status_code == 400
    assert "مدیر" in resp.json()["detail"]


def test_manager_job_title_allows_null_supervisor(client, db_session):
    hr = make_user(db_session, "hr")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    manager = make_personnel(db_session, job_title="مدیر", is_manager=True)
    db_session.commit()

    resp = client.put(
        f"/api/personnel/{manager.id}/access",
        json={"unit_supervisor_user_id": None, "deputy_user_id": dep.id, "ceo_user_id": ceo.id},
        headers=auth_header(hr),
    )
    assert resp.status_code == 200
    assert resp.json()["unit_supervisor_user_id"] is None


def test_regular_job_title_allows_unit_supervisor(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    regular = make_personnel(db_session, job_title="کارشناس")
    db_session.commit()

    resp = client.put(
        f"/api/personnel/{regular.id}/access",
        json={"unit_supervisor_user_id": sup.id, "deputy_user_id": dep.id, "ceo_user_id": ceo.id},
        headers=auth_header(hr),
    )
    assert resp.status_code == 200
    assert resp.json()["unit_supervisor_user_id"] == sup.id


def test_non_hr_role_cannot_set_access(client, db_session):
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    regular = make_personnel(db_session, job_title="کارشناس")
    db_session.commit()

    resp = client.put(
        f"/api/personnel/{regular.id}/access",
        json={"unit_supervisor_user_id": sup.id, "deputy_user_id": dep.id, "ceo_user_id": ceo.id},
        headers=auth_header(sup),
    )
    assert resp.status_code == 403


def test_access_rejects_user_with_wrong_role(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    regular = make_personnel(db_session, job_title="کارشناس")
    db_session.commit()

    # کاربری با نقش «مسئول واحد» به‌عنوان مدیرعامل → پرونده‌ها برای همیشه گیر می‌کردند
    resp = client.put(
        f"/api/personnel/{regular.id}/access",
        json={"unit_supervisor_user_id": sup.id, "deputy_user_id": dep.id, "ceo_user_id": sup.id},
        headers=auth_header(hr),
    )
    assert resp.status_code == 400
    assert "نقش" in resp.json()["detail"]


def test_is_manager_change_blocked_while_open_evaluation_exists(client, db_session):
    """اگر ارزیابی نهایی‌نشده‌ای روی این فرد باز باشد، تغییر is_manager نباید
    اجازه داده شود — وگرنه آن رکورد با انتظارات مسیر جدید ناهماهنگ می‌ماند."""
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session, job_title="کارشناس")
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    )
    assert r.status_code == 201, r.text

    resp = client.patch(
        f"/api/personnel/{personnel.id}", json={"is_manager": True}, headers=auth_header(hr)
    )
    assert resp.status_code == 400
    assert "ارزیابی باز" in resp.json()["detail"]

    # بدون تغییر is_manager همچنان باید بشود ویرایش کرد
    resp = client.patch(
        f"/api/personnel/{personnel.id}", json={"job_title": "کارشناس ارشد"}, headers=auth_header(hr)
    )
    assert resp.status_code == 200
    assert resp.json()["job_title"] == "کارشناس ارشد"


def test_is_manager_change_allowed_once_evaluation_is_finalized(client, db_session):
    from tests.helpers import active_indicators, full_valid_scores

    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session, job_title="کارشناس")
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    indicators = active_indicators(db_session)
    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    )
    evaluation_id = r.json()["id"]
    client.put(
        f"/api/evaluations/{evaluation_id}/scores",
        json={"scores": full_valid_scores(indicators)},
        headers=auth_header(sup),
    )
    client.post(f"/api/evaluations/{evaluation_id}/submit", headers=auth_header(sup))
    client.post(f"/api/evaluations/{evaluation_id}/hr-approve", headers=auth_header(hr))
    client.post(f"/api/evaluations/{evaluation_id}/deputy-approve", headers=auth_header(dep))
    assert (
        client.post(f"/api/evaluations/{evaluation_id}/ceo-finalize", headers=auth_header(ceo)).status_code
        == 200
    )

    resp = client.patch(
        f"/api/personnel/{personnel.id}", json={"is_manager": True}, headers=auth_header(hr)
    )
    assert resp.status_code == 200
    assert resp.json()["is_manager"] is True


def test_access_rejects_inactive_user(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    ceo.is_active = False
    db_session.flush()
    regular = make_personnel(db_session, job_title="کارشناس")
    db_session.commit()

    resp = client.put(
        f"/api/personnel/{regular.id}/access",
        json={"unit_supervisor_user_id": sup.id, "deputy_user_id": dep.id, "ceo_user_id": ceo.id},
        headers=auth_header(hr),
    )
    assert resp.status_code == 400
    assert "غیرفعال" in resp.json()["detail"]
