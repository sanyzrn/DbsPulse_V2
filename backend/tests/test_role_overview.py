"""تست داشبورد نقش‌محور (item 15): هر نقش کاشی‌های متناسب خودش را می‌گیرد."""
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


def _cards(client, user) -> dict[str, float]:
    r = client.get("/api/dashboard/role-overview", headers=auth_header(user))
    assert r.status_code == 200, r.text
    body = r.json()
    return {c["key"]: c["value"] for c in body["cards"]}


def test_role_overview_is_scoped_per_role(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    indicators = active_indicators(db_session)
    eid = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    ).json()["id"]
    client.put(
        f"/api/evaluations/{eid}/scores",
        json={"scores": full_valid_scores(indicators)},
        headers=auth_header(sup),
    )

    # پیش‌نویس: مسئول واحد یک پیش‌نویس باز دارد و یک نفر زیرمجموعه
    sup_cards = _cards(client, sup)
    assert sup_cards["subordinates"] == 1
    assert sup_cards["drafts"] == 1
    assert sup_cards["in_review"] == 0

    client.post(f"/api/evaluations/{eid}/submit", headers=auth_header(sup))

    # پس از ارسال: منابع انسانی یک پرونده در انتظار بررسی دارد
    hr_cards = _cards(client, hr)
    assert hr_cards["awaiting_hr"] == 1
    assert hr_cards["open"] >= 1

    # مسئول واحد اکنون پرونده‌ای در جریان تأیید دارد (نه پیش‌نویس)
    sup_cards = _cards(client, sup)
    assert sup_cards["drafts"] == 0
    assert sup_cards["in_review"] == 1

    client.post(f"/api/evaluations/{eid}/hr-approve", headers=auth_header(hr))

    # معاونت یک پرونده در انتظار تأیید دارد (مسیر عادی)
    dep_cards = _cards(client, dep)
    assert dep_cards["awaiting_me"] == 1
    assert dep_cards["manager_scoring"] == 0

    client.post(f"/api/evaluations/{eid}/deputy-approve", headers=auth_header(dep))

    # مدیرعامل یک پرونده در انتظار تأیید نهایی دارد
    ceo_cards = _cards(client, ceo)
    assert ceo_cards["awaiting_me"] == 1


def test_role_overview_for_employee(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    employee = make_user(db_session, "employee", personnel_id=personnel.id)
    db_session.commit()

    indicators = active_indicators(db_session)
    eid = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    ).json()["id"]
    client.put(
        f"/api/evaluations/{eid}/scores",
        json={"scores": full_valid_scores(indicators)},
        headers=auth_header(sup),
    )
    client.post(f"/api/evaluations/{eid}/submit", headers=auth_header(sup))
    client.post(f"/api/evaluations/{eid}/hr-approve", headers=auth_header(hr))
    client.post(f"/api/evaluations/{eid}/deputy-approve", headers=auth_header(dep))
    client.post(f"/api/evaluations/{eid}/ceo-finalize", headers=auth_header(ceo))

    cards = _cards(client, employee)
    assert cards["finalized"] == 1
    # قبل از رؤیت، یک پرونده در انتظار رؤیت کارمند است
    assert cards["pending_ack"] == 1
