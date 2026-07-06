"""تست‌های Phase 2: پرچم is_manager، مشتق‌شدن stage از status، صفحه‌بندی سمت سرور،
endpoint پیکربندی و داشبورد."""
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


def _run_full_workflow(client, db_session, hr, sup, dep, ceo, personnel) -> int:
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
    assert client.post(f"/api/evaluations/{evaluation_id}/hr-approve", headers=auth_header(hr)).status_code == 200
    assert client.post(f"/api/evaluations/{evaluation_id}/deputy-approve", headers=auth_header(dep)).status_code == 200
    assert client.post(f"/api/evaluations/{evaluation_id}/ceo-finalize", headers=auth_header(ceo)).status_code == 200
    return evaluation_id


def test_config_endpoint_returns_business_rules(client, db_session):
    user = make_user(db_session, "unit_supervisor")
    db_session.commit()

    r = client.get("/api/config", headers=auth_header(user))
    assert r.status_code == 200
    body = r.json()
    assert body["evidence_min_words"] == 15
    assert body["evidence_exempt_score"] == 3
    assert body["general_section_weight"] == 0.6
    assert body["specialized_section_weight"] == 0.4


def test_setting_is_manager_clears_supervisor_access(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    r = client.patch(
        f"/api/personnel/{personnel.id}", json={"is_manager": True}, headers=auth_header(hr)
    )
    assert r.status_code == 200
    assert r.json()["is_manager"] is True

    r = client.get(f"/api/personnel/{personnel.id}/access", headers=auth_header(hr))
    assert r.json()["unit_supervisor_user_id"] is None


def test_create_evaluation_without_supervisor_gives_distinct_message(client, db_session):
    """مدیر سابق که دیگر مدیر نیست ولی مسئول واحد هم ندارد نباید پیام گمراه‌کننده بگیرد."""
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, None, dep, ceo)  # بدون مسئول واحد
    db_session.commit()

    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    )
    assert r.status_code == 400
    assert "مسئول واحد برای این پرسنل تعریف نشده" in r.json()["detail"]


def test_evaluation_list_is_paginated_and_searchable(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    p1 = make_personnel(db_session, full_name="جوینده یکتا")
    p2 = make_personnel(db_session, full_name="شخص دیگر")
    make_access(db_session, p1, sup, dep, ceo)
    make_access(db_session, p2, sup, dep, ceo)
    db_session.commit()

    for p in (p1, p2):
        r = client.post(
            "/api/evaluations", json={"subject_personnel_id": p.id}, headers=auth_header(sup)
        )
        assert r.status_code == 201

    r = client.get("/api/evaluations", headers=auth_header(hr))
    body = r.json()
    assert body["total"] >= 2
    # نام پرسنل داخل خود آیتم embed شده (بدون fetch جداگانه)
    names = {item["subject_full_name"] for item in body["items"]}
    assert {"جوینده یکتا", "شخص دیگر"} <= names
    # stage از status مشتق می‌شود
    assert all(item["stage"] == "supervisor_scoring" for item in body["items"] if item["status"] == "draft")

    # جست‌وجو با نام پرسنل
    r = client.get("/api/evaluations", params={"q": "جوینده"}, headers=auth_header(hr))
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["subject_full_name"] == "جوینده یکتا"

    # فیلتر وضعیت + صفحه‌بندی
    r = client.get(
        "/api/evaluations", params={"status": "draft", "limit": 1, "offset": 0}, headers=auth_header(hr)
    )
    body = r.json()
    assert body["total"] >= 2
    assert len(body["items"]) == 1


def test_personnel_list_is_paginated_and_searchable(client, db_session):
    hr = make_user(db_session, "hr")
    make_personnel(db_session, full_name="کارمند الف")
    make_personnel(db_session, full_name="کارمند ب")
    db_session.commit()

    r = client.get("/api/personnel", params={"q": "الف"}, headers=auth_header(hr))
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["full_name"] == "کارمند الف"

    r = client.get("/api/personnel", params={"limit": 1}, headers=auth_header(hr))
    assert len(r.json()["items"]) == 1


def test_dashboard_overview_reflects_finalized_evaluation(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session, org_unit="واحد داشبورد")
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    _run_full_workflow(client, db_session, hr, sup, dep, ceo, personnel)

    r = client.get("/api/dashboard/overview", headers=auth_header(hr))
    assert r.status_code == 200
    body = r.json()
    assert body["total_evaluations"] >= 1
    assert body["avg_final_pct"] is not None
    assert any(u["org_unit"] == "واحد داشبورد" for u in body["by_org_unit"])

    r = client.get(f"/api/dashboard/personnel/{personnel.id}/trend", headers=auth_header(hr))
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get(f"/api/dashboard/personnel/{personnel.id}/radar", headers=auth_header(hr))
    assert r.status_code == 200
    assert len(r.json()) > 0


def test_pipeline_counts_by_status(client, db_session):
    hr = make_user(db_session, "hr")
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

    r = client.get("/api/dashboard/pipeline", headers=auth_header(hr))
    assert r.status_code == 200
    stats = {row["status"]: row for row in r.json()}
    # هر پنج وضعیت حاضرند (حتی با شمارش صفر) و پیش‌نویس تازه شمرده شده
    assert set(stats) == {"draft", "submitted", "hr_approved", "deputy_approved", "finalized"}
    assert stats["draft"]["count"] >= 1
    assert stats["draft"]["oldest_created_at"] is not None

    # فقط HR
    assert client.get("/api/dashboard/pipeline", headers=auth_header(sup)).status_code == 403


def test_excel_export_returns_xlsx_for_hr_only(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()
    client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    )

    r = client.get("/api/evaluations/export.xlsx", headers=auth_header(hr))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    # فایل xlsx یک آرشیو zip است (سرآغاز PK)
    assert r.content[:2] == b"PK"

    assert client.get("/api/evaluations/export.xlsx", headers=auth_header(sup)).status_code == 403
