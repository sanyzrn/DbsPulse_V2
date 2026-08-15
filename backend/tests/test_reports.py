"""تست‌های گزارش‌های تحلیلی HR (خلاصهٔ فیلترشده، ریز شاخص، مقایسهٔ فرد با واحد،
خروجی Excel ترکیبی)."""
from tests.helpers import (
    active_indicators,
    auth_header,
    make_access,
    make_personnel,
    make_user,
)

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _finalize_for(client, db_session, hr, sup, dep, ceo, personnel, score=3):
    indicators = active_indicators(db_session)
    eid = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    ).json()["id"]
    # امتیازهای ۱ و ۵ شواهد اجباری دارند (حداقل ۳ کلمه)
    evidence = {"evidence_text": "شواهد عینی کافی برای این امتیاز"} if score in (1, 5) else {}
    scores = [{"indicator_id": i.id, "score": score, **evidence} for i in indicators]
    client.put(f"/api/evaluations/{eid}/scores", json={"scores": scores}, headers=auth_header(sup))
    client.post(f"/api/evaluations/{eid}/submit", headers=auth_header(sup))
    client.post(f"/api/evaluations/{eid}/hr-approve", headers=auth_header(hr))
    client.post(f"/api/evaluations/{eid}/deputy-approve", headers=auth_header(dep))
    client.post(f"/api/evaluations/{eid}/ceo-finalize", headers=auth_header(ceo))
    return eid


def _actors(db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    return hr, sup, dep, ceo


def test_report_summary_and_org_unit_filter(client, db_session, no_cohort_suppression):
    hr, sup, dep, ceo = _actors(db_session)
    p_sales = make_personnel(db_session, org_unit="واحدRPT-فروش")
    p_it = make_personnel(db_session, org_unit="واحدRPT-فناوری")
    make_access(db_session, p_sales, sup, dep, ceo)
    make_access(db_session, p_it, sup, dep, ceo)
    db_session.commit()

    _finalize_for(client, db_session, hr, sup, dep, ceo, p_sales, score=3)  # 60%
    _finalize_for(client, db_session, hr, sup, dep, ceo, p_it, score=5)  # 100%

    # خلاصهٔ کل
    r = client.get("/api/dashboard/report/summary", headers=auth_header(hr))
    assert r.status_code == 200, r.text
    body = r.json()
    units = {u["org_unit"]: u for u in body["by_org_unit"]}
    assert units["واحدRPT-فروش"]["avg_final_pct"] == 60.0
    assert units["واحدRPT-فناوری"]["avg_final_pct"] == 100.0
    assert len(body["by_indicator"]) == 20
    # همهٔ شاخص‌ها در فروش ۳ و در فناوری ۵ → میانگین ۴
    assert all(i["avg_score"] == 4.0 for i in body["by_indicator"])

    # فیلتر واحد سازمانی
    r = client.get(
        "/api/dashboard/report/summary",
        params={"org_unit": "واحدRPT-فروش"},
        headers=auth_header(hr),
    )
    body = r.json()
    assert body["total_evaluations"] == 1
    assert {u["org_unit"] for u in body["by_org_unit"]} == {"واحدRPT-فروش"}
    assert all(i["avg_score"] == 3.0 for i in body["by_indicator"])


def test_indicator_breakdown_by_unit(client, db_session, no_cohort_suppression):
    hr, sup, dep, ceo = _actors(db_session)
    p_sales = make_personnel(db_session, org_unit="واحدIND-فروش")
    p_it = make_personnel(db_session, org_unit="واحدIND-فناوری")
    make_access(db_session, p_sales, sup, dep, ceo)
    make_access(db_session, p_it, sup, dep, ceo)
    db_session.commit()
    _finalize_for(client, db_session, hr, sup, dep, ceo, p_sales, score=2)
    _finalize_for(client, db_session, hr, sup, dep, ceo, p_it, score=4)

    indicator_id = active_indicators(db_session)[0].id
    r = client.get(f"/api/dashboard/report/indicator/{indicator_id}", headers=auth_header(hr))
    assert r.status_code == 200, r.text
    body = r.json()
    by_unit = {u["org_unit"]: u["avg_score"] for u in body["by_org_unit"]}
    assert by_unit["واحدIND-فروش"] == 2.0
    assert by_unit["واحدIND-فناوری"] == 4.0
    assert body["overall_avg"] == 3.0

    # شاخص ناموجود → 404
    assert client.get("/api/dashboard/report/indicator/999999", headers=auth_header(hr)).status_code == 404


def test_employee_vs_unit(client, db_session, no_cohort_suppression):
    hr, sup, dep, ceo = _actors(db_session)
    me = make_personnel(db_session, org_unit="واحدEVU")
    peer = make_personnel(db_session, org_unit="واحدEVU")
    make_access(db_session, me, sup, dep, ceo)
    make_access(db_session, peer, sup, dep, ceo)
    db_session.commit()
    _finalize_for(client, db_session, hr, sup, dep, ceo, me, score=2)  # 40%
    _finalize_for(client, db_session, hr, sup, dep, ceo, peer, score=5)  # 100%

    r = client.get(
        "/api/dashboard/report/employee-vs-unit",
        params={"personnel_id": me.id},
        headers=auth_header(hr),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["employee_avg"] == 40.0
    assert body["unit_avg"] == 70.0  # میانگین (۴۰ + ۱۰۰) / ۲
    assert body["unit_evaluation_count"] == 2
    assert len(body["per_evaluation"]) == 1


def test_report_export_xlsx_and_rbac(client, db_session):
    hr, sup, dep, ceo = _actors(db_session)
    p = make_personnel(db_session, org_unit="واحدEXP")
    make_access(db_session, p, sup, dep, ceo)
    db_session.commit()
    _finalize_for(client, db_session, hr, sup, dep, ceo, p)

    r = client.get("/api/dashboard/report/export.xlsx", headers=auth_header(hr))
    assert r.status_code == 200
    assert r.headers["content-type"] == _XLSX_MIME
    assert r.content[:2] == b"PK"

    # فقط HR
    assert client.get("/api/dashboard/report/summary", headers=auth_header(sup)).status_code == 403


def test_report_rejects_reversed_date_range(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()
    r = client.get(
        "/api/dashboard/report/summary",
        params={"created_from": "2026-05-01", "created_to": "2026-01-01"},
        headers=auth_header(hr),
    )
    assert r.status_code == 400
