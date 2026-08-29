"""P0-03 (نیمهٔ کوتاه‌مدت) — مسئولِ HR برای هر پرونده.

سه مرحلهٔ دیگر همیشه صاحب مشخصی داشتند و گذارشان برابری `current_user.id` با آن
صاحب را لازم دارد. مرحلهٔ HR این را نداشت: هر کاربر HR روی هر پرونده‌ای می‌توانست
تأیید یا برگشت بزند، پس در سازمانی با چند نفر HR پاسخ سؤال «مسئولِ این پرونده که
بود؟» وجود نداشت — فقط «چه کسی کلیک کرد».
"""
from app.models.enums import Capability
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


def _submitted_case(client, db_session):
    hr = make_user(db_session, "hr", capabilities=[Capability.view_audit_log])
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    evaluation = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    ).json()
    client.put(
        f"/api/evaluations/{evaluation['id']}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(sup),
    )
    client.post(f"/api/evaluations/{evaluation['id']}/submit", headers=auth_header(sup))
    return {"id": evaluation["id"], "hr": hr, "sup": sup, "dep": dep, "ceo": ceo}


def test_a_fresh_case_has_no_hr_owner(client, db_session):
    case = _submitted_case(client, db_session)

    detail = client.get(f"/api/evaluations/{case['id']}", headers=auth_header(case["hr"])).json()

    assert detail["hr_user_id"] is None
    assert detail["hr_username"] is None


def test_any_hr_can_claim_an_unowned_case(client, db_session):
    case = _submitted_case(client, db_session)

    r = client.post(f"/api/evaluations/{case['id']}/hr-claim", headers=auth_header(case["hr"]))

    assert r.status_code == 200
    assert r.json()["hr_user_id"] == case["hr"].id
    assert r.json()["hr_username"] == case["hr"].username


def test_claiming_an_owned_case_is_refused(client, db_session):
    case = _submitted_case(client, db_session)
    other_hr = make_user(db_session, "hr")
    db_session.commit()
    client.post(f"/api/evaluations/{case['id']}/hr-claim", headers=auth_header(case["hr"]))

    r = client.post(f"/api/evaluations/{case['id']}/hr-claim", headers=auth_header(other_hr))

    assert r.status_code == 409
    assert case["hr"].username in r.json()["detail"]


def test_acting_on_an_unowned_case_claims_it_implicitly(client, db_session):
    """کسی که اقدام می‌کند مسئول می‌شود — بدون این، «کی کلیک کرد» تنها ردی بود که می‌ماند."""
    case = _submitted_case(client, db_session)

    r = client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(case["hr"]))

    assert r.status_code == 200
    assert r.json()["hr_user_id"] == case["hr"].id


def test_another_hr_cannot_act_on_a_claimed_case(client, db_session):
    case = _submitted_case(client, db_session)
    other_hr = make_user(db_session, "hr")
    db_session.commit()
    client.post(f"/api/evaluations/{case['id']}/hr-claim", headers=auth_header(case["hr"]))

    r = client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(other_hr))

    assert r.status_code == 403
    assert "کاربر دیگری" in r.json()["detail"]


def test_the_owner_can_still_act(client, db_session):
    case = _submitted_case(client, db_session)
    client.post(f"/api/evaluations/{case['id']}/hr-claim", headers=auth_header(case["hr"]))

    r = client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(case["hr"]))

    assert r.status_code == 200
    assert r.json()["status"] == "hr_approved"


def test_ownership_does_not_change_the_wrong_stage_error(client, db_session):
    """«هنوز نوبت HR نشده» نباید با «مالِ کاربر دیگری است» قاطی شود."""
    case = _submitted_case(client, db_session)
    client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(case["hr"]))

    # حالا در مرحلهٔ معاونت است، نه HR
    r = client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(case["hr"]))

    assert r.status_code == 400
    assert "انتظار بررسی منابع انسانی" in r.json()["detail"]


def test_handover_moves_ownership_and_notifies(client, db_session):
    case = _submitted_case(client, db_session)
    successor = make_user(db_session, "hr")
    db_session.commit()
    client.post(f"/api/evaluations/{case['id']}/hr-claim", headers=auth_header(case["hr"]))

    r = client.post(
        f"/api/evaluations/{case['id']}/hr-handover",
        json={"new_hr_user_id": successor.id, "reason": "مرخصی طولانی"},
        headers=auth_header(case["hr"]),
    )

    assert r.status_code == 200
    assert r.json()["hr_user_id"] == successor.id

    # مسئول جدید می‌تواند اقدام کند، قبلی نه
    assert (
        client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(case["hr"])).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(successor)
        ).status_code
        == 200
    )

    notifications = client.get("/api/notifications", headers=auth_header(successor)).json()
    rows = notifications["items"] if isinstance(notifications, dict) else notifications
    assert any(row["evaluation_record_id"] == case["id"] for row in rows)


def test_handover_is_audited_with_both_sides(client, db_session):
    case = _submitted_case(client, db_session)
    successor = make_user(db_session, "hr")
    db_session.commit()
    client.post(f"/api/evaluations/{case['id']}/hr-claim", headers=auth_header(case["hr"]))
    client.post(
        f"/api/evaluations/{case['id']}/hr-handover",
        json={"new_hr_user_id": successor.id, "reason": "بازتوزیع بار کاری"},
        headers=auth_header(case["hr"]),
    )

    events = client.get(
        "/api/audit-log",
        params={"event_type": "hr_case_handed_over"},
        headers=auth_header(case["hr"]),
    ).json()
    rows = events["items"] if isinstance(events, dict) and "items" in events else events
    entry = next(row for row in rows if row["evaluation_record_id"] == case["id"])
    assert entry["old_value"]["hr_user_id"] == case["hr"].id
    assert entry["new_value"]["hr_user_id"] == successor.id
    assert "بازتوزیع" in entry["new_value"]["reason"]


def test_handover_requires_a_reason_and_a_real_hr_user(client, db_session):
    case = _submitted_case(client, db_session)
    not_hr = make_user(db_session, "deputy")
    db_session.commit()
    client.post(f"/api/evaluations/{case['id']}/hr-claim", headers=auth_header(case["hr"]))

    no_reason = client.post(
        f"/api/evaluations/{case['id']}/hr-handover",
        json={"new_hr_user_id": not_hr.id, "reason": "  "},
        headers=auth_header(case["hr"]),
    )
    assert no_reason.status_code == 422

    wrong_role = client.post(
        f"/api/evaluations/{case['id']}/hr-handover",
        json={"new_hr_user_id": not_hr.id, "reason": "دلیل معتبر"},
        headers=auth_header(case["hr"]),
    )
    assert wrong_role.status_code == 400


def test_cancel_stays_available_to_any_hr_regardless_of_owner(client, db_session):
    """لغو راه فرار است؛ اگر خودش پشت مالکیت قفل می‌شد، دوباره پروندهٔ گیرکرده می‌ساخت."""
    case = _submitted_case(client, db_session)
    other_hr = make_user(db_session, "hr")
    db_session.commit()
    client.post(f"/api/evaluations/{case['id']}/hr-claim", headers=auth_header(case["hr"]))

    r = client.post(
        f"/api/evaluations/{case['id']}/cancel",
        json={"reason": "مسئول قبلی از سازمان رفت و پرونده بلاتکلیف ماند"},
        headers=auth_header(other_hr),
    )

    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_non_hr_roles_cannot_claim_or_hand_over(client, db_session):
    case = _submitted_case(client, db_session)

    assert (
        client.post(f"/api/evaluations/{case['id']}/hr-claim", headers=auth_header(case["dep"])).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/evaluations/{case['id']}/hr-handover",
            json={"new_hr_user_id": case["hr"].id, "reason": "تلاش"},
            headers=auth_header(case["sup"]),
        ).status_code
        == 403
    )
