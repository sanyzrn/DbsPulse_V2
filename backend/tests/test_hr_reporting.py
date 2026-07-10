"""تست‌های ممیزی نهایی: فیلترهای ترکیبی فهرست ارزیابی‌ها، خروجی‌های Excel جدید،
endpoint واحدهای سازمانی و محافظ قفل‌نشدن حساب HR."""
from datetime import date, timedelta

from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _finalized_evaluation(client, db_session, org_unit="واحد گزارش"):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session, org_unit=org_unit)
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
    client.post(f"/api/evaluations/{eid}/hr-approve", headers=auth_header(hr))
    client.post(f"/api/evaluations/{eid}/deputy-approve", headers=auth_header(dep))
    client.post(f"/api/evaluations/{eid}/ceo-finalize", headers=auth_header(ceo))
    return eid, hr


def test_evaluation_list_combinable_filters(client, db_session):
    eid, hr = _finalized_evaluation(client, db_session, org_unit="واحد فیلتر")

    def fetch(**params):
        r = client.get("/api/evaluations", params=params, headers=auth_header(hr))
        assert r.status_code == 200, r.text
        return {item["id"] for item in r.json()["items"]}

    # فیلتر واحد سازمانی
    assert eid in fetch(org_unit="واحد فیلتر")
    assert eid not in fetch(org_unit="واحد ناموجود")

    # بازه تاریخ (امروز داخل بازه است؛ بازه گذشته آن را ندارد)
    today = date.today().isoformat()
    old = (date.today() - timedelta(days=30)).isoformat()
    assert eid in fetch(created_from=today, created_to=today)
    assert eid not in fetch(created_to=old)

    # بازه امتیاز نهایی: نمرهٔ همه ۳ است → نهایی ۶۰٪
    assert eid in fetch(min_final_pct=50, max_final_pct=70)
    assert eid not in fetch(min_final_pct=90)

    # ترکیب چند فیلتر با هم
    assert eid in fetch(org_unit="واحد فیلتر", status="finalized", min_final_pct=50)
    assert eid not in fetch(org_unit="واحد فیلتر", status="draft")


def test_evaluations_export_respects_filters(client, db_session):
    _, hr = _finalized_evaluation(client, db_session, org_unit="واحد الف")

    r = client.get(
        "/api/evaluations/export.xlsx",
        params={"org_unit": "واحد الف", "status": "finalized"},
        headers=auth_header(hr),
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == _XLSX_MIME
    assert r.content[:2] == b"PK"  # امضای فایل zip/xlsx


def test_org_units_endpoint_is_distinct_and_hr_only(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    make_personnel(db_session, org_unit="واحد تکراری")
    make_personnel(db_session, org_unit="واحد تکراری")
    db_session.commit()

    r = client.get("/api/personnel/org-units", headers=auth_header(hr))
    assert r.status_code == 200
    units = r.json()
    assert units.count("واحد تکراری") == 1

    assert client.get("/api/personnel/org-units", headers=auth_header(sup)).status_code == 403


def test_personnel_export_returns_xlsx_for_hr_only(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    make_personnel(db_session)
    db_session.commit()

    r = client.get("/api/personnel/export.xlsx", headers=auth_header(hr))
    assert r.status_code == 200
    assert r.content[:2] == b"PK"

    assert client.get("/api/personnel/export.xlsx", headers=auth_header(sup)).status_code == 403


def test_improvement_plans_export_returns_xlsx(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()
    r = client.get("/api/improvement-plans/export.xlsx", headers=auth_header(hr))
    assert r.status_code == 200
    assert r.content[:2] == b"PK"


def test_hr_cannot_lock_out_own_account(client, db_session):
    hr = make_user(db_session, "hr")
    other_hr = make_user(db_session, "hr")
    db_session.commit()

    # غیرفعال‌کردن حساب خود → ۴۰۰
    r = client.patch(f"/api/users/{hr.id}", json={"is_active": False}, headers=auth_header(hr))
    assert r.status_code == 400
    # گرفتن نقش HR از خود → ۴۰۰
    r = client.patch(f"/api/users/{hr.id}", json={"role": "deputy"}, headers=auth_header(hr))
    assert r.status_code == 400
    # اما مدیریت حساب HR دیگر همچنان مجاز است
    r = client.patch(
        f"/api/users/{other_hr.id}", json={"is_active": False}, headers=auth_header(hr)
    )
    assert r.status_code == 200
