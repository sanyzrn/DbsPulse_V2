"""تست‌های دوره‌های (کمپین) ارزیابی: تک‌دوره باز، برچسب خودکار، پیشرفت و بستن."""
from tests.helpers import auth_header, make_access, make_personnel, make_user


def _create_period(client, hr, name="دوره آزمون") -> dict:
    r = client.post(
        "/api/periods",
        json={"name": name, "starts_on": "2026-07-01", "ends_on": "2026-09-30"},
        headers=auth_header(hr),
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_only_one_open_period_at_a_time(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()

    period = _create_period(client, hr)
    assert period["status"] == "open"

    r = client.post(
        "/api/periods",
        json={"name": "دوره دوم", "starts_on": "2026-10-01", "ends_on": "2026-12-30"},
        headers=auth_header(hr),
    )
    assert r.status_code == 400
    assert "هنوز باز است" in r.json()["detail"]

    # بعد از بستن، دوره جدید مجاز است
    r = client.post(f"/api/periods/{period['id']}/close", headers=auth_header(hr))
    assert r.status_code == 200
    assert r.json()["status"] == "closed"
    assert r.json()["closed_at"] is not None

    r = client.post(
        "/api/periods",
        json={"name": "دوره دوم", "starts_on": "2026-10-01", "ends_on": "2026-12-30"},
        headers=auth_header(hr),
    )
    assert r.status_code == 201


def test_period_dates_must_be_in_order(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()
    r = client.post(
        "/api/periods",
        json={"name": "برعکس", "starts_on": "2026-09-30", "ends_on": "2026-07-01"},
        headers=auth_header(hr),
    )
    assert r.status_code == 422


def test_new_evaluations_are_tagged_with_open_period(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    period = _create_period(client, hr)

    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    )
    assert r.status_code == 201
    assert r.json()["period_id"] == period["id"]


def test_evaluation_without_open_period_has_no_tag(client, db_session):
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    )
    assert r.status_code == 201
    assert r.json()["period_id"] is None


def test_period_progress_tracks_cohort(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    p1 = make_personnel(db_session, full_name="عضو دوره یک")
    p2 = make_personnel(db_session, full_name="عضو دوره دو")
    make_access(db_session, p1, sup, dep, ceo)
    make_access(db_session, p2, sup, dep, ceo)
    db_session.commit()

    period = _create_period(client, hr)

    r = client.get(f"/api/periods/{period['id']}/progress", headers=auth_header(hr))
    assert r.status_code == 200
    body = r.json()
    # دیتابیس تست seed هم دارد؛ فقط نسبت به دو نفرِ همین تست قضاوت می‌کنیم
    assert body["eligible"] >= 2
    assert body["started"] == 0
    names = [x["full_name"] for x in body["not_started"]]
    assert "عضو دوره یک" in names and "عضو دوره دو" in names

    # با شروع ارزیابی یک نفر، از فهرست جامانده‌ها خارج می‌شود
    client.post("/api/evaluations", json={"subject_personnel_id": p1.id}, headers=auth_header(sup))
    r = client.get(f"/api/periods/{period['id']}/progress", headers=auth_header(hr))
    body = r.json()
    assert body["started"] == 1
    assert body["finalized"] == 0
    names = [x["full_name"] for x in body["not_started"]]
    assert "عضو دوره یک" not in names and "عضو دوره دو" in names


def test_opening_period_notifies_evaluators(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    db_session.commit()

    _create_period(client, hr, name="دوره اطلاع‌رسانی")

    r = client.get("/api/notifications", headers=auth_header(sup))
    assert any("دوره ارزیابی «دوره اطلاع‌رسانی» آغاز شد" in n["message"] for n in r.json()["items"])


def test_periods_are_hr_only(client, db_session):
    sup = make_user(db_session, "unit_supervisor")
    db_session.commit()
    assert client.get("/api/periods", headers=auth_header(sup)).status_code == 403
    r = client.post(
        "/api/periods",
        json={"name": "x", "starts_on": "2026-07-01", "ends_on": "2026-09-30"},
        headers=auth_header(sup),
    )
    assert r.status_code == 403
