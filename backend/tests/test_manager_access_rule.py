from tests.helpers import auth_header, make_personnel, make_user


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
