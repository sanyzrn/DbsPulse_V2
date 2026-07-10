"""تست‌های پاسخ threaded به کامنت‌های پرونده (item 9)."""
from sqlalchemy import select

from app.models.notification import Notification
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


def _submitted_evaluation(client, db_session):
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
    client.post(f"/api/evaluations/{eid}/submit", headers=auth_header(sup))
    return eid, hr, sup, dep, ceo


def test_evaluator_can_reply_to_reviewer_comment(client, db_session):
    eid, hr, sup, dep, ceo = _submitted_evaluation(client, db_session)

    # HR کامنت سطح‌بالا ثبت می‌کند
    parent = client.post(
        f"/api/evaluations/{eid}/comments",
        json={"comment_text": "لطفاً شواهد شاخص سوم را کامل کنید"},
        headers=auth_header(hr),
    ).json()
    assert parent["parent_comment_id"] is None

    # مسئول واحد (ارزیاب) به همان کامنت پاسخ می‌دهد
    r = client.post(
        f"/api/evaluations/{eid}/comments",
        json={"comment_text": "شواهد اضافه شد", "parent_comment_id": parent["id"]},
        headers=auth_header(sup),
    )
    assert r.status_code == 201, r.text
    reply = r.json()
    assert reply["parent_comment_id"] == parent["id"]
    # پاسخ در همان نخِ مرحلهٔ کامنتِ والد می‌ماند
    assert reply["stage"] == parent["stage"]

    # در جزئیات پرونده هم پاسخ دیده می‌شود
    detail = client.get(f"/api/evaluations/{eid}", headers=auth_header(hr)).json()
    ids = {c["id"]: c for c in detail["comments"]}
    assert ids[reply["id"]]["parent_comment_id"] == parent["id"]

    # نویسندهٔ کامنتِ والد (HR) از پاسخ اعلان می‌گیرد
    notif = db_session.scalar(
        select(Notification).where(
            Notification.user_id == hr.id,
            Notification.type == "comment_reply_added",
        )
    )
    assert notif is not None


def test_reply_to_reply_is_rejected(client, db_session):
    eid, hr, sup, dep, ceo = _submitted_evaluation(client, db_session)
    parent = client.post(
        f"/api/evaluations/{eid}/comments",
        json={"comment_text": "کامنت والد"},
        headers=auth_header(hr),
    ).json()
    reply = client.post(
        f"/api/evaluations/{eid}/comments",
        json={"comment_text": "پاسخ اول", "parent_comment_id": parent["id"]},
        headers=auth_header(sup),
    ).json()

    # پاسخ به پاسخ (عمق ۲) ممنوع است
    r = client.post(
        f"/api/evaluations/{eid}/comments",
        json={"comment_text": "پاسخ به پاسخ", "parent_comment_id": reply["id"]},
        headers=auth_header(hr),
    )
    assert r.status_code == 400, r.text


def test_reply_parent_must_belong_to_same_record(client, db_session):
    eid, hr, sup, dep, ceo = _submitted_evaluation(client, db_session)
    parent = client.post(
        f"/api/evaluations/{eid}/comments",
        json={"comment_text": "کامنت پروندهٔ اول"},
        headers=auth_header(hr),
    ).json()

    # یک پروندهٔ دوم
    eid2, hr2, sup2, *_ = _submitted_evaluation(client, db_session)
    r = client.post(
        f"/api/evaluations/{eid2}/comments",
        json={"comment_text": "پاسخ با والدِ پروندهٔ دیگر", "parent_comment_id": parent["id"]},
        headers=auth_header(hr2),
    )
    assert r.status_code == 404, r.text
