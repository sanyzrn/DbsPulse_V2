from tests.helpers import auth_header, make_personnel, make_user


def test_only_hr_can_create_personnel(client, db_session):
    sup = make_user(db_session, "unit_supervisor")
    db_session.commit()

    r = client.post(
        "/api/personnel",
        json={
            "personnel_code": "X-1",
            "full_name": "کسی",
            "job_title": "کارشناس",
            "org_unit": "واحد",
            "contract_start_date": "2025-01-01",
            "contract_end_date": "2026-01-01",
        },
        headers=auth_header(sup),
    )
    assert r.status_code == 403


def test_anonymous_request_is_rejected(client, db_session):
    r = client.get("/api/personnel")
    assert r.status_code == 401


def test_only_hr_can_manage_indicators(client, db_session):
    sup = make_user(db_session, "unit_supervisor")
    hr = make_user(db_session, "hr")
    db_session.commit()

    r = client.post(
        "/api/indicators",
        json={"section": "general", "category": "دسته آزمایشی", "description": "شرح", "display_order": 99},
        headers=auth_header(sup),
    )
    assert r.status_code == 403

    r = client.post(
        "/api/indicators",
        json={"section": "general", "category": "دسته آزمایشی", "description": "شرح", "display_order": 99},
        headers=auth_header(hr),
    )
    assert r.status_code == 201


def test_personnel_detail_requires_relevant_access(client, db_session):
    hr = make_user(db_session, "hr")
    make_user(db_session, "unit_supervisor")
    sup2 = make_user(db_session, "unit_supervisor")
    personnel = make_personnel(db_session)
    db_session.commit()

    # sup2 has no relationship to this personnel record at all
    r = client.get(f"/api/personnel/{personnel.id}", headers=auth_header(sup2))
    assert r.status_code == 403

    # HR always has access
    r = client.get(f"/api/personnel/{personnel.id}", headers=auth_header(hr))
    assert r.status_code == 200


def test_only_hr_sees_full_user_list(client, db_session):
    sup = make_user(db_session, "unit_supervisor")
    hr = make_user(db_session, "hr")
    db_session.commit()

    r = client.get("/api/users", headers=auth_header(sup))
    assert r.status_code == 403

    r = client.get("/api/users", headers=auth_header(hr))
    assert r.status_code == 200
