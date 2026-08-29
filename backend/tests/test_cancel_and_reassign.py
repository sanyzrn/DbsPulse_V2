"""P0-02 — راه خروج از پروندهٔ گیرکرده.

تا پیش از این، تنها گذار پایانی «نهایی‌سازی» بود. اگر تأییدکننده‌ای از سازمان می‌رفت،
مرحله‌اش هرگز کامل نمی‌شد (گذار، برابری `current_user.id` با مسئول ثبت‌شده را لازم
دارد) و ایندکس یکتای جزئی هم اجازهٔ ساخت پروندهٔ جایگزین نمی‌داد — آن پرسنل عملاً برای
همیشه غیرقابل‌ارزیابی می‌شد و تنها درمانش SQL دستی روی پروداکشن بود.
"""
from app.models.enums import Capability, EvaluationStatus
from app.models.evaluation import EvaluationRecord
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


def _open_case(client, db_session):
    """یک پروندهٔ باز در وضعیت submitted، با همهٔ بازیگرانش."""
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
    return {
        "id": evaluation["id"],
        "personnel": personnel,
        "hr": hr,
        "sup": sup,
        "dep": dep,
        "ceo": ceo,
    }


# ---------------------------------------------------------------- cancel


def test_hr_cancels_an_open_case_with_a_reason(client, db_session):
    case = _open_case(client, db_session)

    r = client.post(
        f"/api/evaluations/{case['id']}/cancel",
        json={"reason": "مسئول واحد از سازمان خارج شد"},
        headers=auth_header(case["hr"]),
    )

    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    # پروندهٔ لغوشده در هیچ مرحله‌ای نیست
    assert r.json()["stage"] is None


def test_cancel_requires_a_reason(client, db_session):
    case = _open_case(client, db_session)

    r = client.post(
        f"/api/evaluations/{case['id']}/cancel", json={"reason": "   "}, headers=auth_header(case["hr"])
    )

    assert r.status_code == 422


def test_only_hr_can_cancel(client, db_session):
    case = _open_case(client, db_session)

    for actor in ("sup", "dep", "ceo"):
        r = client.post(
            f"/api/evaluations/{case['id']}/cancel",
            json={"reason": "تلاش غیرمجاز"},
            headers=auth_header(case[actor]),
        )
        assert r.status_code == 403, actor


def test_cancel_records_the_reason_as_a_visible_comment_and_an_audit_event(client, db_session):
    case = _open_case(client, db_session)
    reason = "پرسنل پیش از پایان ارزیابی استعفا داد"

    client.post(
        f"/api/evaluations/{case['id']}/cancel",
        json={"reason": reason},
        headers=auth_header(case["hr"]),
    )

    detail = client.get(f"/api/evaluations/{case['id']}", headers=auth_header(case["hr"])).json()
    assert any(reason in c["comment_text"] for c in detail["comments"])

    events = client.get(
        "/api/audit-log", params={"event_type": "evaluation_cancelled"}, headers=auth_header(case["hr"])
    ).json()
    rows = events["items"] if isinstance(events, dict) and "items" in events else events
    assert any(row["evaluation_record_id"] == case["id"] for row in rows)


def test_a_replacement_evaluation_can_be_opened_after_cancelling(client, db_session):
    """قلب این یافته: بدون اصلاح predicate ایندکس، لغو هیچ چیزی را حل نمی‌کرد."""
    case = _open_case(client, db_session)

    blocked = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": case["personnel"].id},
        headers=auth_header(case["sup"]),
    )
    assert blocked.status_code == 409, "پرسنل نباید هم‌زمان دو پروندهٔ باز داشته باشد"

    client.post(
        f"/api/evaluations/{case['id']}/cancel",
        json={"reason": "تخصیص اشتباه"},
        headers=auth_header(case["hr"]),
    )

    replacement = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": case["personnel"].id},
        headers=auth_header(case["sup"]),
    )
    assert replacement.status_code == 201
    assert replacement.json()["id"] != case["id"]


def test_a_cancelled_case_cannot_be_cancelled_or_advanced_again(client, db_session):
    case = _open_case(client, db_session)
    client.post(
        f"/api/evaluations/{case['id']}/cancel",
        json={"reason": "لغو اول"},
        headers=auth_header(case["hr"]),
    )

    again = client.post(
        f"/api/evaluations/{case['id']}/cancel",
        json={"reason": "لغو دوم"},
        headers=auth_header(case["hr"]),
    )
    assert again.status_code == 400

    advanced = client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(case["hr"]))
    assert advanced.status_code == 400


def test_finalized_cases_cannot_be_cancelled(client, db_session):
    case = _open_case(client, db_session)
    client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(case["hr"]))
    client.post(f"/api/evaluations/{case['id']}/deputy-approve", headers=auth_header(case["dep"]))
    client.post(f"/api/evaluations/{case['id']}/ceo-finalize", headers=auth_header(case["ceo"]))

    r = client.post(
        f"/api/evaluations/{case['id']}/cancel",
        json={"reason": "بعد از نهایی‌شدن"},
        headers=auth_header(case["hr"]),
    )

    assert r.status_code == 400


def test_cancelled_cases_stop_counting_as_open(client, db_session):
    """پروندهٔ لغوشده نباید در «پرونده‌های باز» یا جاروی SLA دیده شود."""
    from app.services.workflow import IS_OPEN_RECORD

    case = _open_case(client, db_session)
    assert db_session.query(EvaluationRecord).filter(
        EvaluationRecord.id == case["id"], IS_OPEN_RECORD
    ).count() == 1

    client.post(
        f"/api/evaluations/{case['id']}/cancel",
        json={"reason": "لغو"},
        headers=auth_header(case["hr"]),
    )
    db_session.expire_all()

    assert db_session.query(EvaluationRecord).filter(
        EvaluationRecord.id == case["id"], IS_OPEN_RECORD
    ).count() == 0


# -------------------------------------------------------------- reassign


def test_hr_reassigns_a_departed_approver_and_the_case_moves_again(client, db_session):
    """سناریوی واقعی: معاونت می‌رود، پرونده گیر می‌کند، HR جایگزین می‌گذارد، کار ادامه می‌یابد."""
    case = _open_case(client, db_session)
    client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(case["hr"]))

    replacement_deputy = make_user(db_session, "deputy")
    db_session.commit()

    # معاونت جدید هنوز مسئول این پرونده نیست
    blocked = client.post(
        f"/api/evaluations/{case['id']}/deputy-approve", headers=auth_header(replacement_deputy)
    )
    assert blocked.status_code == 403

    r = client.post(
        f"/api/evaluations/{case['id']}/reassign",
        json={
            "stage_field": "deputy_user_id",
            "new_user_id": replacement_deputy.id,
            "reason": "معاونت قبلی از سازمان خارج شد",
        },
        headers=auth_header(case["hr"]),
    )
    assert r.status_code == 200
    assert r.json()["deputy_user_id"] == replacement_deputy.id

    moved = client.post(
        f"/api/evaluations/{case['id']}/deputy-approve", headers=auth_header(replacement_deputy)
    )
    assert moved.status_code == 200
    assert moved.json()["status"] == "deputy_approved"


def test_reassign_keeps_the_scores(client, db_session):
    case = _open_case(client, db_session)
    before = client.get(f"/api/evaluations/{case['id']}", headers=auth_header(case["hr"])).json()
    replacement = make_user(db_session, "ceo")
    db_session.commit()

    client.post(
        f"/api/evaluations/{case['id']}/reassign",
        json={"stage_field": "ceo_user_id", "new_user_id": replacement.id, "reason": "بازنشستگی"},
        headers=auth_header(case["hr"]),
    )

    after = client.get(f"/api/evaluations/{case['id']}", headers=auth_header(case["hr"])).json()
    assert len(after["scores"]) == len(before["scores"]) == 20


def test_reassign_rejects_a_user_with_the_wrong_role(client, db_session):
    case = _open_case(client, db_session)
    wrong_role = make_user(db_session, "unit_supervisor")
    db_session.commit()

    r = client.post(
        f"/api/evaluations/{case['id']}/reassign",
        json={"stage_field": "deputy_user_id", "new_user_id": wrong_role.id, "reason": "اشتباه"},
        headers=auth_header(case["hr"]),
    )

    assert r.status_code == 400
    assert "معاونت" in r.json()["detail"]


def test_reassign_rejects_an_inactive_user(client, db_session):
    case = _open_case(client, db_session)
    inactive = make_user(db_session, "deputy")
    inactive.is_active = False
    db_session.commit()

    r = client.post(
        f"/api/evaluations/{case['id']}/reassign",
        json={"stage_field": "deputy_user_id", "new_user_id": inactive.id, "reason": "اشتباه"},
        headers=auth_header(case["hr"]),
    )

    assert r.status_code == 400


def test_reassign_cannot_make_someone_their_own_evaluator(client, db_session):
    """همان نامساوی P0-10 — بازتخصیص نباید در آن سوراخ باز کند."""
    case = _open_case(client, db_session)
    himself = make_user(db_session, "deputy", personnel_id=case["personnel"].id)
    db_session.commit()

    r = client.post(
        f"/api/evaluations/{case['id']}/reassign",
        json={"stage_field": "deputy_user_id", "new_user_id": himself.id, "reason": "تلاش"},
        headers=auth_header(case["hr"]),
    )

    assert r.status_code == 400
    assert "ارزیابِ خودش" in r.json()["detail"]


def test_only_hr_can_reassign(client, db_session):
    case = _open_case(client, db_session)
    replacement = make_user(db_session, "deputy")
    db_session.commit()

    r = client.post(
        f"/api/evaluations/{case['id']}/reassign",
        json={"stage_field": "deputy_user_id", "new_user_id": replacement.id, "reason": "تلاش"},
        headers=auth_header(case["dep"]),
    )

    assert r.status_code == 403


def test_cannot_reassign_a_finalized_case(client, db_session):
    case = _open_case(client, db_session)
    client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(case["hr"]))
    client.post(f"/api/evaluations/{case['id']}/deputy-approve", headers=auth_header(case["dep"]))
    client.post(f"/api/evaluations/{case['id']}/ceo-finalize", headers=auth_header(case["ceo"]))
    replacement = make_user(db_session, "ceo")
    db_session.commit()

    r = client.post(
        f"/api/evaluations/{case['id']}/reassign",
        json={"stage_field": "ceo_user_id", "new_user_id": replacement.id, "reason": "دیر"},
        headers=auth_header(case["hr"]),
    )

    assert r.status_code == 400


def test_reassign_notifies_the_new_owner(client, db_session):
    case = _open_case(client, db_session)
    client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(case["hr"]))
    replacement = make_user(db_session, "deputy")
    db_session.commit()

    client.post(
        f"/api/evaluations/{case['id']}/reassign",
        json={"stage_field": "deputy_user_id", "new_user_id": replacement.id, "reason": "خروج"},
        headers=auth_header(case["hr"]),
    )

    notifications = client.get("/api/notifications", headers=auth_header(replacement)).json()
    rows = notifications["items"] if isinstance(notifications, dict) else notifications
    assert any(row["evaluation_record_id"] == case["id"] for row in rows), (
        "مسئول جدید باید خبردار شود، وگرنه پرونده دوباره همان‌جا می‌ماند"
    )


def test_manager_path_has_no_supervisor_stage_to_reassign(client, db_session):
    hr = make_user(db_session, "hr")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    manager = make_personnel(db_session, job_title="مدیر", is_manager=True)
    make_access(db_session, manager, None, dep, ceo)
    db_session.commit()

    evaluation = client.post(
        "/api/evaluations", json={"subject_personnel_id": manager.id}, headers=auth_header(dep)
    ).json()
    replacement = make_user(db_session, "unit_supervisor")
    db_session.commit()

    r = client.post(
        f"/api/evaluations/{evaluation['id']}/reassign",
        json={
            "stage_field": "unit_supervisor_user_id",
            "new_user_id": replacement.id,
            "reason": "ندارد",
        },
        headers=auth_header(hr),
    )

    assert r.status_code == 400
    assert "مدیر" in r.json()["detail"]


def test_cancelled_status_is_a_real_enum_member(db_session):
    assert EvaluationStatus.cancelled.value == "cancelled"


# ---------------------------------------------- orphaned-case detection


def test_sweep_reports_cases_whose_owner_went_inactive(client, db_session):
    """HR نباید موقع تمدید قرارداد تازه بفهمد پرونده‌ای گیر کرده است."""
    from app.services.scheduled import run_orphaned_case_sweep

    case = _open_case(client, db_session)
    client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(case["hr"]))

    # معاونتِ مسئول این مرحله از سازمان خارج می‌شود
    case["dep"].is_active = False
    db_session.flush()

    assert run_orphaned_case_sweep(db_session) >= 1

    notifications = client.get("/api/notifications", headers=auth_header(case["hr"])).json()
    rows = notifications["items"] if isinstance(notifications, dict) else notifications
    assert any("گیر کرده" in row["message"] for row in rows)


def test_sweep_stays_quiet_while_every_owner_is_active(client, db_session):
    from app.services.scheduled import run_orphaned_case_sweep

    case = _open_case(client, db_session)
    client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(case["hr"]))

    assert run_orphaned_case_sweep(db_session) == 0


def test_sweep_ignores_cancelled_cases(client, db_session):
    """پروندهٔ لغوشده دیگر گیر نکرده — نباید تا ابد یادآوری بسازد."""
    from app.services.scheduled import run_orphaned_case_sweep

    case = _open_case(client, db_session)
    client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(case["hr"]))
    case["dep"].is_active = False
    db_session.flush()
    client.post(
        f"/api/evaluations/{case['id']}/cancel",
        json={"reason": "معاونت رفت و جایگزینی نبود"},
        headers=auth_header(case["hr"]),
    )
    db_session.expire_all()

    assert run_orphaned_case_sweep(db_session) == 0
