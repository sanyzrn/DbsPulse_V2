from tests.helpers import auth_header, make_access, make_personnel, make_user


def test_only_hr_can_view_audit_log(client, db_session):
    sup = make_user(db_session, "unit_supervisor")
    db_session.commit()

    r = client.get("/api/audit-log", headers=auth_header(sup))
    assert r.status_code == 403


def test_indicator_creation_is_logged(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()

    client.post(
        "/api/indicators",
        json={"section": "general", "category": "دسته لاگ", "description": "شرح", "display_order": 1},
        headers=auth_header(hr),
    )

    r = client.get("/api/audit-log", params={"event_type": "indicator_created"}, headers=auth_header(hr))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert body["items"][0]["event_type"] == "indicator_created"
    assert body["items"][0]["actor_username"] == hr.username


def test_evaluation_status_changes_are_logged_and_filterable(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    r = client.post("/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup))
    evaluation_id = r.json()["id"]

    r = client.get(
        "/api/audit-log", params={"evaluation_record_id": evaluation_id}, headers=auth_header(hr)
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["event_type"] == "status_changed"
    assert body["items"][0]["evaluation_record_id"] == evaluation_id
    assert body["items"][0]["evaluation_code"] is not None


def test_audit_log_filters_by_actor_personnel_and_org_unit(client, db_session):
    """گزارش رویدادها باید بتواند سابقهٔ یک کاربر، یک پرسنل یا یک واحد سازمانی
    مشخص را جدا و دقیق نشان دهد — نه فقط نوع رویداد و بازهٔ تاریخ."""
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel_a = make_personnel(db_session, org_unit="واحد الف")
    personnel_b = make_personnel(db_session, org_unit="واحد ب")
    make_access(db_session, personnel_a, sup, dep, ceo)
    make_access(db_session, personnel_b, sup, dep, ceo)
    db_session.commit()

    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel_a.id}, headers=auth_header(sup)
    )
    eval_a = r.json()["id"]
    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel_b.id}, headers=auth_header(sup)
    )
    eval_b = r.json()["id"]

    # فیلتر انجام‌دهنده: هر دو رویداد را sup ساخته، hr هیچ‌کدام را نساخته
    r = client.get("/api/audit-log", params={"actor_user_id": sup.id}, headers=auth_header(hr))
    ids = {item["evaluation_record_id"] for item in r.json()["items"]}
    assert {eval_a, eval_b}.issubset(ids)
    r = client.get("/api/audit-log", params={"actor_user_id": hr.id}, headers=auth_header(hr))
    assert eval_a not in {item["evaluation_record_id"] for item in r.json()["items"]}

    # فیلتر پرسنل مشخص: فقط رویدادهای پروندهٔ همان فرد
    r = client.get(
        "/api/audit-log", params={"personnel_id": personnel_a.id}, headers=auth_header(hr)
    )
    ids = {item["evaluation_record_id"] for item in r.json()["items"]}
    assert eval_a in ids
    assert eval_b not in ids

    # فیلتر واحد سازمانی: فقط رویدادهای پرونده‌های همان واحد
    r = client.get("/api/audit-log", params={"org_unit": "واحد ب"}, headers=auth_header(hr))
    ids = {item["evaluation_record_id"] for item in r.json()["items"]}
    assert eval_b in ids
    assert eval_a not in ids


def test_audit_log_pagination(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()
    for i in range(3):
        client.post(
            "/api/indicators",
            json={"section": "general", "category": f"دسته {i}", "description": "شرح", "display_order": i},
            headers=auth_header(hr),
        )

    r = client.get("/api/audit-log", params={"limit": 2, "offset": 0}, headers=auth_header(hr))
    body = r.json()
    assert len(body["items"]) == 2
    assert body["total"] >= 3
