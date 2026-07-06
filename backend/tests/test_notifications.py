"""تست‌های اعلان درون‌برنامه‌ای و فهرست قراردادهای رو به انقضا."""
from datetime import date, timedelta

from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


def _submit_evaluation(client, db_session, sup, personnel):
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
    assert client.post(f"/api/evaluations/{evaluation_id}/submit", headers=auth_header(sup)).status_code == 200
    return evaluation_id


def test_workflow_transitions_notify_next_in_chain(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session, full_name="گیرنده اعلان")
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    evaluation_id = _submit_evaluation(client, db_session, sup, personnel)

    # submit → همه کاربران HR اعلان می‌گیرند
    r = client.get("/api/notifications", headers=auth_header(hr))
    body = r.json()
    assert body["unread"] >= 1
    assert any("صف بررسی منابع انسانی" in n["message"] for n in body["items"])
    assert body["items"][0]["link"] == f"/evaluations/{evaluation_id}"

    # hr_approve → معاونت اعلان می‌گیرد
    client.post(f"/api/evaluations/{evaluation_id}/hr-approve", headers=auth_header(hr))
    r = client.get("/api/notifications", headers=auth_header(dep))
    assert any("در انتظار بررسی و تأیید شماست" in n["message"] for n in r.json()["items"])

    # deputy_approve → مدیرعامل؛ ceo_finalize → ارزیاب (مسئول واحد)
    client.post(f"/api/evaluations/{evaluation_id}/deputy-approve", headers=auth_header(dep))
    r = client.get("/api/notifications", headers=auth_header(ceo))
    assert any("در انتظار تأیید نهایی شماست" in n["message"] for n in r.json()["items"])

    client.post(f"/api/evaluations/{evaluation_id}/ceo-finalize", headers=auth_header(ceo))
    r = client.get("/api/notifications", headers=auth_header(sup))
    assert any("تأیید نهایی شد" in n["message"] for n in r.json()["items"])


def test_return_notifies_previous_stage_owner(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    evaluation_id = _submit_evaluation(client, db_session, sup, personnel)
    client.post(
        f"/api/evaluations/{evaluation_id}/return",
        json={"reason": "نیاز به اصلاح"},
        headers=auth_header(hr),
    )
    r = client.get("/api/notifications", headers=auth_header(sup))
    assert any("برگشت داده شد" in n["message"] for n in r.json()["items"])


def test_notifications_are_private_and_markable(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    _submit_evaluation(client, db_session, sup, personnel)

    r = client.get("/api/notifications", headers=auth_header(hr))
    notification_id = r.json()["items"][0]["id"]
    unread_before = r.json()["unread"]
    assert unread_before >= 1

    # کاربر دیگر نمی‌تواند اعلان HR را بخواند/علامت بزند
    r = client.post(f"/api/notifications/{notification_id}/read", headers=auth_header(sup))
    assert r.status_code == 404
    # اعلان‌های sup فقط مال خودش است (اعلان HR در فهرست sup نیست)
    r = client.get("/api/notifications", headers=auth_header(sup))
    assert all(n["id"] != notification_id for n in r.json()["items"])

    # علامت‌گذاری تکی و سراسری
    r = client.post(f"/api/notifications/{notification_id}/read", headers=auth_header(hr))
    assert r.status_code == 200
    assert r.json()["read_at"] is not None

    assert client.post("/api/notifications/read-all", headers=auth_header(hr)).status_code == 204
    r = client.get("/api/notifications", headers=auth_header(hr))
    assert r.json()["unread"] == 0


def test_expiring_contracts_watchlist(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    soon = make_personnel(
        db_session,
        full_name="قرارداد رو به پایان",
        contract_end_date=date.today() + timedelta(days=20),
    )
    make_personnel(
        db_session,
        full_name="قرارداد بلندمدت",
        contract_end_date=date.today() + timedelta(days=300),
    )
    make_access(db_session, soon, sup, dep, ceo)
    db_session.commit()

    r = client.get("/api/dashboard/expiring-contracts", params={"days": 60}, headers=auth_header(hr))
    assert r.status_code == 200
    rows = r.json()
    names = [x["full_name"] for x in rows]
    assert "قرارداد رو به پایان" in names
    assert "قرارداد بلندمدت" not in names
    entry = next(x for x in rows if x["full_name"] == "قرارداد رو به پایان")
    assert entry["days_remaining"] == 20
    assert entry["has_open_evaluation"] is False

    # با شروع ارزیابی، پرچم «ارزیابی باز» true می‌شود
    client.post("/api/evaluations", json={"subject_personnel_id": soon.id}, headers=auth_header(sup))
    r = client.get("/api/dashboard/expiring-contracts", params={"days": 60}, headers=auth_header(hr))
    entry = next(x for x in r.json() if x["full_name"] == "قرارداد رو به پایان")
    assert entry["has_open_evaluation"] is True

    # فقط HR
    r = client.get("/api/dashboard/expiring-contracts", headers=auth_header(sup))
    assert r.status_code == 403
