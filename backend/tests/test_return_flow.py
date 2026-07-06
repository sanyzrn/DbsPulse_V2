"""تست‌های «برگشت پرونده»: هر تأییدکننده می‌تواند با ذکر دلیل پرونده را یک مرحله
عقب بفرستد؛ امتیازها حفظ و دلیل به‌صورت کامنت + رویداد audit ثبت می‌شود."""
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
