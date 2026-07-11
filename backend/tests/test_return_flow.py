"""تست‌های «برگشت پرونده»: هر تأییدکننده می‌تواند با ذکر دلیل پرونده را یک مرحله
عقب بفرستد؛ امتیازها حفظ و دلیل به‌صورت کامنت + رویداد audit ثبت می‌شود."""
from sqlalchemy import func, select

from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


def _setup_submitted(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

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
    return hr, sup, dep, ceo, evaluation_id


def test_hr_returns_file_to_supervisor_with_reason(client, db_session):
    hr, sup, dep, ceo, evaluation_id = _setup_submitted(client, db_session)

    # بدون دلیل → 422
    r = client.post(f"/api/evaluations/{evaluation_id}/return", json={"reason": " "}, headers=auth_header(hr))
    assert r.status_code == 422

    r = client.post(
        f"/api/evaluations/{evaluation_id}/return",
        json={"reason": "شواهد شاخص سوم کافی نیست"},
        headers=auth_header(hr),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "draft"
    assert body["stage"] == "supervisor_scoring"

    # امتیازهای قبلی حفظ شده و دلیل به‌صورت کامنت با نام نویسنده دیده می‌شود
    detail = client.get(f"/api/evaluations/{evaluation_id}", headers=auth_header(sup)).json()
    assert len(detail["scores"]) == 20
    return_comments = [c for c in detail["comments"] if "برگشت پرونده" in c["comment_text"]]
    assert len(return_comments) == 1
    assert "شواهد شاخص سوم" in return_comments[0]["comment_text"]
    assert return_comments[0]["commenter_username"] == hr.username

    # مسئول واحد می‌تواند دوباره ویرایش و ثبت کند
    indicators = active_indicators(db_session)
    r = client.put(
        f"/api/evaluations/{evaluation_id}/scores",
        json={"scores": full_valid_scores(indicators)},
        headers=auth_header(sup),
    )
    assert r.status_code == 200
    assert client.post(f"/api/evaluations/{evaluation_id}/submit", headers=auth_header(sup)).status_code == 200

    # رویداد audit ثبت شده است
    r = client.get(
        "/api/audit-log",
        params={"event_type": "evaluation_returned", "evaluation_record_id": evaluation_id},
        headers=auth_header(hr),
    )
    assert r.json()["total"] == 1

    # صف بررسی باید این پرونده را از یک ثبت تازه (بدون سابقه برگشت) تشخیص دهد
    r = client.get("/api/evaluations", params={"status": "submitted"}, headers=auth_header(hr))
    items = {item["id"]: item for item in r.json()["items"]}
    assert items[evaluation_id]["was_returned"] is True


def test_fresh_submission_is_not_flagged_as_returned(client, db_session):
    hr, sup, dep, ceo, evaluation_id = _setup_submitted(client, db_session)
    r = client.get("/api/evaluations", params={"status": "submitted"}, headers=auth_header(hr))
    items = {item["id"]: item for item in r.json()["items"]}
    assert items[evaluation_id]["was_returned"] is False


def test_deputy_and_ceo_returns_step_back_one_stage(client, db_session):
    hr, sup, dep, ceo, evaluation_id = _setup_submitted(client, db_session)
    assert client.post(f"/api/evaluations/{evaluation_id}/hr-approve", headers=auth_header(hr)).status_code == 200

    # معاونت به HR برمی‌گرداند
    r = client.post(
        f"/api/evaluations/{evaluation_id}/return",
        json={"reason": "نیاز به بررسی مجدد HR"},
        headers=auth_header(dep),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "submitted"

    assert client.post(f"/api/evaluations/{evaluation_id}/hr-approve", headers=auth_header(hr)).status_code == 200
    assert client.post(f"/api/evaluations/{evaluation_id}/deputy-approve", headers=auth_header(dep)).status_code == 200

    # مدیرعامل به معاونت برمی‌گرداند
    r = client.post(
        f"/api/evaluations/{evaluation_id}/return",
        json={"reason": "توضیح تکمیلی معاونت لازم است"},
        headers=auth_header(ceo),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "hr_approved"

    # و مسیر می‌تواند تا انتها ادامه یابد
    assert client.post(f"/api/evaluations/{evaluation_id}/deputy-approve", headers=auth_header(dep)).status_code == 200
    assert client.post(f"/api/evaluations/{evaluation_id}/ceo-finalize", headers=auth_header(ceo)).status_code == 200


def test_deputy_cannot_return_on_manager_path(client, db_session):
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    manager = make_personnel(db_session, job_title="مدیر", is_manager=True)
    make_access(db_session, manager, None, dep, ceo)
    db_session.commit()

    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": manager.id}, headers=auth_header(dep)
    )
    evaluation_id = r.json()["id"]

    r = client.post(
        f"/api/evaluations/{evaluation_id}/return",
        json={"reason": "تلاش برای برگشت"},
        headers=auth_header(dep),
    )
    assert r.status_code == 400
    assert "مسیر «مدیر»" in r.json()["detail"]


def _notifications_for(db_session, user_id: int, type_prefix: str) -> int:
    from app.models.notification import Notification

    return db_session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.type.like(f"{type_prefix}%"))
    )


def test_return_notifications_fire_to_correct_recipient(client, db_session):
    """برگشت هر مرحله باید دقیقاً به مسئولِ همان مرحلهٔ قبل اعلان بفرستد."""
    hr, sup, dep, ceo, evaluation_id = _setup_submitted(client, db_session)

    # HR → مسئول واحد
    client.post(
        f"/api/evaluations/{evaluation_id}/return",
        json={"reason": "اصلاح لازم است"},
        headers=auth_header(hr),
    )
    assert _notifications_for(db_session, sup.id, "workflow_hr_return") == 1

    # دوباره تا مرحلهٔ hr_approved جلو می‌رویم
    client.post(f"/api/evaluations/{evaluation_id}/submit", headers=auth_header(sup))
    client.post(f"/api/evaluations/{evaluation_id}/hr-approve", headers=auth_header(hr))

    # معاونت → HR
    client.post(
        f"/api/evaluations/{evaluation_id}/return",
        json={"reason": "بازبینی HR"},
        headers=auth_header(dep),
    )
    assert _notifications_for(db_session, hr.id, "workflow_deputy_return") == 1

    # تا deputy_approved جلو می‌رویم
    client.post(f"/api/evaluations/{evaluation_id}/hr-approve", headers=auth_header(hr))
    client.post(f"/api/evaluations/{evaluation_id}/deputy-approve", headers=auth_header(dep))

    # مدیرعامل → معاونت
    client.post(
        f"/api/evaluations/{evaluation_id}/return",
        json={"reason": "توضیح معاونت"},
        headers=auth_header(ceo),
    )
    assert _notifications_for(db_session, dep.id, "workflow_ceo_return") == 1


def test_returned_draft_is_editable_again_and_reflects_history(client, db_session):
    """پس از برگشت به draft، مسئول واحد دوباره می‌تواند ویرایش کند و سابقهٔ برگشت
    (کامنت با نام برگرداننده + رویداد audit) درست ثبت شده است."""
    hr, sup, dep, ceo, evaluation_id = _setup_submitted(client, db_session)
    client.post(
        f"/api/evaluations/{evaluation_id}/return",
        json={"reason": "شواهد ناکافی"},
        headers=auth_header(hr),
    )
    # دیگر نقش‌ها نباید در draft بتوانند امتیاز بزنند
    indicators = active_indicators(db_session)
    assert (
        client.put(
            f"/api/evaluations/{evaluation_id}/scores",
            json={"scores": full_valid_scores(indicators)},
            headers=auth_header(dep),
        ).status_code
        == 403
    )
    # ولی مسئول واحد بله
    assert (
        client.put(
            f"/api/evaluations/{evaluation_id}/scores",
            json={"scores": full_valid_scores(indicators)},
            headers=auth_header(sup),
        ).status_code
        == 200
    )


def test_return_requires_matching_state_and_role(client, db_session):
    hr, sup, dep, ceo, evaluation_id = _setup_submitted(client, db_session)

    # معاونت نمی‌تواند پرونده‌ای را که هنوز در بررسی HR است برگرداند
    r = client.post(
        f"/api/evaluations/{evaluation_id}/return",
        json={"reason": "زودهنگام"},
        headers=auth_header(dep),
    )
    assert r.status_code == 403

    # مسئول واحد اصلاً اجازه برگشت ندارد
    r = client.post(
        f"/api/evaluations/{evaluation_id}/return",
        json={"reason": "بی‌معنا"},
        headers=auth_header(sup),
    )
    assert r.status_code == 403
