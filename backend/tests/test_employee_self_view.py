"""تست‌های نقش «کارمند» (employee): کارنامه من + رؤیت رسمی نتیجه (R13a).

مهم‌ترین بخش: کارمند نباید چیزی بیش از نتیجه نهایی ارزیابی خودش ببیند —
نه پرونده در جریان، نه پرونده دیگران، نه شواهد و کامنت‌های داخلی زنجیره.
"""
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.notification import Notification
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


def _make_chain(db):
    hr = make_user(db, "hr")
    sup = make_user(db, "unit_supervisor")
    dep = make_user(db, "deputy")
    ceo = make_user(db, "ceo")
    return hr, sup, dep, ceo


def _finalize_evaluation(client, db, hr, sup, dep, ceo, personnel) -> int:
    indicators = active_indicators(db)
    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    )
    assert r.status_code == 201, r.text
    evaluation_id = r.json()["id"]
    client.put(
        f"/api/evaluations/{evaluation_id}/scores",
        json={"scores": full_valid_scores(indicators)},
        headers=auth_header(sup),
    )
    assert client.post(
        f"/api/evaluations/{evaluation_id}/submit", headers=auth_header(sup)
    ).status_code == 200
    assert client.post(
        f"/api/evaluations/{evaluation_id}/hr-approve", headers=auth_header(hr)
    ).status_code == 200
    assert client.post(
        f"/api/evaluations/{evaluation_id}/deputy-approve", headers=auth_header(dep)
    ).status_code == 200
    assert client.post(
        f"/api/evaluations/{evaluation_id}/ceo-finalize", headers=auth_header(ceo)
    ).status_code == 200
    return evaluation_id


def test_my_evaluations_only_own_finalized(client, db_session):
    hr, sup, dep, ceo = _make_chain(db_session)
    mine = make_personnel(db_session, full_name="کارمند خودم")
    other = make_personnel(db_session, full_name="کارمند دیگر")
    make_access(db_session, mine, sup, dep, ceo)
    make_access(db_session, other, sup, dep, ceo)
    employee = make_user(db_session, "employee", personnel_id=mine.id)
    db_session.commit()

    finalized_id = _finalize_evaluation(client, db_session, hr, sup, dep, ceo, mine)
    _finalize_evaluation(client, db_session, hr, sup, dep, ceo, other)
    # پرونده باز جدید برای خودم (پس از نهایی شدن قبلی مجاز است)
    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": mine.id}, headers=auth_header(sup)
    )
    assert r.status_code == 201

    r = client.get("/api/me/evaluations", headers=auth_header(employee))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [finalized_id]
    item = body["items"][0]
    assert item["final_weighted_pct"] is not None
    assert item["acknowledged_at"] is None
    # فیلدهای داخلی زنجیره در نمای کارمند وجود ندارند
    assert "scores" not in item and "evaluator_comment" not in item


def test_employee_list_evaluations_no_leak(client, db_session):
    """شاخه صریح employee در GET /api/evaluations — نباید در مسیر «HR همه را می‌بیند» بیفتد."""
    hr, sup, dep, ceo = _make_chain(db_session)
    mine = make_personnel(db_session, full_name="کارمند لیست")
    other = make_personnel(db_session, full_name="غریبه لیست")
    make_access(db_session, mine, sup, dep, ceo)
    make_access(db_session, other, sup, dep, ceo)
    employee = make_user(db_session, "employee", personnel_id=mine.id)
    orphan = make_user(db_session, "employee", personnel_id=mine.id)
    orphan.personnel_id = None
    db_session.commit()

    my_final = _finalize_evaluation(client, db_session, hr, sup, dep, ceo, mine)
    other_final = _finalize_evaluation(client, db_session, hr, sup, dep, ceo, other)

    r = client.get("/api/evaluations", headers=auth_header(employee))
    assert r.status_code == 200
    ids = [item["id"] for item in r.json()["items"]]
    assert my_final in ids
    assert other_final not in ids

    # کارمند بدون پیوند پرسنلی هیچ‌چیز نمی‌بیند (نه همه‌چیز!)
    r = client.get("/api/evaluations", headers=auth_header(orphan))
    assert r.status_code == 200
    assert r.json()["total"] == 0

    # جزئیات کامل پرونده (شواهد/کامنت‌ها) برای کارمند بسته است
    assert client.get(
        f"/api/evaluations/{my_final}", headers=auth_header(employee)
    ).status_code == 403


def test_acknowledge_happy_path_with_audit_and_hr_notification(client, db_session):
    hr, sup, dep, ceo = _make_chain(db_session)
    personnel = make_personnel(db_session, full_name="رؤیت‌کننده")
    make_access(db_session, personnel, sup, dep, ceo)
    employee = make_user(db_session, "employee", personnel_id=personnel.id)
    db_session.commit()

    evaluation_id = _finalize_evaluation(client, db_session, hr, sup, dep, ceo, personnel)

    r = client.post(
        f"/api/me/evaluations/{evaluation_id}/acknowledge", headers=auth_header(employee)
    )
    assert r.status_code == 200, r.text
    assert r.json()["acknowledged_at"] is not None

    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.event_type == "evaluation_acknowledged",
            AuditLog.evaluation_record_id == evaluation_id,
        )
    )
    assert audit is not None and audit.actor_user_id == employee.id

    hr_notes = list(
        db_session.scalars(
            select(Notification).where(
                Notification.user_id == hr.id,
                Notification.type == "evaluation_acknowledged",
            )
        )
    )
    assert any("رؤیت" in n.message for n in hr_notes)

    # رؤیت دوباره ممنوع
    r = client.post(
        f"/api/me/evaluations/{evaluation_id}/acknowledge", headers=auth_header(employee)
    )
    assert r.status_code == 400


def test_acknowledge_rejects_foreign_and_open_evaluations(client, db_session):
    hr, sup, dep, ceo = _make_chain(db_session)
    mine = make_personnel(db_session, full_name="صاحب پرونده")
    other = make_personnel(db_session, full_name="پرونده غریبه")
    make_access(db_session, mine, sup, dep, ceo)
    make_access(db_session, other, sup, dep, ceo)
    employee = make_user(db_session, "employee", personnel_id=mine.id)
    db_session.commit()

    _finalize_evaluation(client, db_session, hr, sup, dep, ceo, mine)
    other_final = _finalize_evaluation(client, db_session, hr, sup, dep, ceo, other)

    # پرونده دیگران: 404 (وجودش هم لو نمی‌رود)
    assert client.post(
        f"/api/me/evaluations/{other_final}/acknowledge", headers=auth_header(employee)
    ).status_code == 404

    # پرونده باز خودم: هنوز نهایی نشده → 400
    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": mine.id}, headers=auth_header(sup)
    )
    open_id = r.json()["id"]
    assert client.post(
        f"/api/me/evaluations/{open_id}/acknowledge", headers=auth_header(employee)
    ).status_code == 400


def test_employee_user_requires_personnel_link(client, db_session):
    hr = make_user(db_session, "hr")
    personnel = make_personnel(db_session)
    db_session.commit()

    r = client.post(
        "/api/users",
        json={"username": "emp_no_link", "password": "Password123!", "role": "employee"},
        headers=auth_header(hr),
    )
    assert r.status_code == 422

    r = client.post(
        "/api/users",
        json={
            "username": "emp_linked",
            "password": "Password123!",
            "role": "employee",
            "personnel_id": personnel.id,
        },
        headers=auth_header(hr),
    )
    assert r.status_code == 201, r.text
    assert r.json()["personnel_id"] == personnel.id


def test_finalize_notifies_employee(client, db_session):
    hr, sup, dep, ceo = _make_chain(db_session)
    personnel = make_personnel(db_session, full_name="گیرنده ابلاغ")
    make_access(db_session, personnel, sup, dep, ceo)
    employee = make_user(db_session, "employee", personnel_id=personnel.id)
    db_session.commit()

    _finalize_evaluation(client, db_session, hr, sup, dep, ceo, personnel)

    notes = list(
        db_session.scalars(
            select(Notification).where(
                Notification.user_id == employee.id,
                Notification.type == "evaluation_finalized_self",
            )
        )
    )
    assert len(notes) == 1
    assert notes[0].link == "/me"


def test_employee_cannot_touch_workflow_or_admin_endpoints(client, db_session):
    hr, sup, dep, ceo = _make_chain(db_session)
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    employee = make_user(db_session, "employee", personnel_id=personnel.id)
    db_session.commit()

    evaluation_id = _finalize_evaluation(client, db_session, hr, sup, dep, ceo, personnel)
    headers = auth_header(employee)

    assert client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=headers
    ).status_code == 403
    assert client.post(f"/api/evaluations/{evaluation_id}/hr-approve", headers=headers).status_code == 403
    assert client.get("/api/dashboard/overview", headers=headers).status_code == 403
    assert client.get("/api/users", headers=headers).status_code == 403
    assert client.get("/api/audit-log", headers=headers).status_code == 403
    assert client.get(f"/api/evaluations/{evaluation_id}/summary.pdf", headers=headers).status_code == 403
    # فهرست پرسنل برای کارمند خالی برمی‌گردد (fail-closed)
    r = client.get("/api/personnel", headers=headers)
    assert r.status_code == 200 and r.json()["total"] == 0
