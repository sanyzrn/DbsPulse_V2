"""تست‌های پاس QA دوم: رفع باگ‌ها (توکن نامعتبر، سقف کلمات شواهد، قفل چرخهٔ عمر
اهداف، پرسنل غیرفعال، ۴۰۴ دسترسی، اعتبارسنجی بازهٔ فیلتر) و قابلیت‌های جدید
گزارش‌گیری/فیلتر HR (فیلترها و مرتب‌سازی پرسنل، فیلتر و خروجی کاربران، بازهٔ تاریخ و
خروجی گزارش رویدادها)."""
from datetime import UTC, date, datetime, timedelta

import jwt

from app.core.config import settings
from app.core.constants import CONDITIONAL_RENEWAL_RECOMMENDATION
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _finalize(client, db_session, hr, sup, dep, ceo, personnel):
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
    return eid


# ---------------------------------------------------------------- باگ‌ها

def test_malformed_token_sub_returns_401_not_500(client):
    """توکنی که sub غیرعددی دارد نباید به 500 (ValueError کنترل‌نشده) منجر شود."""
    now = datetime.now(UTC)
    bad = jwt.encode(
        {"sub": "not-a-number", "role": "hr", "tv": 0, "type": "access", "iat": now,
         "exp": now + timedelta(minutes=5)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    r = client.get("/api/users", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401


def test_submit_rejects_evidence_over_max_words(client, db_session):
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
    scores = full_valid_scores(indicators)
    # ۴۱ کلمه > سقف ۴۰
    scores[0]["evidence_text"] = " ".join(["کلمه"] * 41)
    client.put(f"/api/evaluations/{eid}/scores", json={"scores": scores}, headers=auth_header(sup))
    r = client.post(f"/api/evaluations/{eid}/submit", headers=auth_header(sup))
    assert r.status_code == 400
    assert "حداکثر" in r.json()["detail"]


def test_goal_cannot_be_added_to_completed_plan(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    # نمرهٔ ۲ برای همه → نهایی ۴۰٪ که در بازهٔ «تمدید مشروط» نیست؛ برای ساخت برنامه
    # بهبود به نتیجهٔ مشروط نیاز داریم، پس رکورد را مستقیم دستکاری می‌کنیم.
    eid = _finalize(client, db_session, hr, sup, dep, ceo, personnel)
    from app.models.evaluation import EvaluationRecord

    rec = db_session.get(EvaluationRecord, eid)
    rec.recommendation = CONDITIONAL_RENEWAL_RECOMMENDATION
    db_session.commit()

    plan = client.post(
        "/api/improvement-plans",
        json={"evaluation_record_id": eid, "title": "برنامه", "review_date": "2026-09-01",
              "goals": ["هدف اول"]},
        headers=auth_header(hr),
    ).json()
    plan_id = plan["id"]

    client.post(f"/api/improvement-plans/{plan_id}/complete", headers=auth_header(hr))
    r = client.post(
        f"/api/improvement-plans/{plan_id}/goals",
        json={"description": "هدف جدید"},
        headers=auth_header(hr),
    )
    assert r.status_code == 409


def test_cannot_start_evaluation_for_inactive_personnel(client, db_session):
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session, status="inactive")
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    )
    assert r.status_code == 400
    assert "غیرفعال" in r.json()["detail"]


def test_duplicate_open_evaluation_returns_evaluation_id(client, db_session):
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    first = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    ).json()["id"]
    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    )
    assert r.status_code == 409
    assert r.json()["detail"]["evaluation_id"] == first


def test_get_access_unknown_personnel_returns_404(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()
    r = client.get("/api/personnel/999999/access", headers=auth_header(hr))
    assert r.status_code == 404


def test_evaluations_list_rejects_min_greater_than_max(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()
    r = client.get(
        "/api/evaluations", params={"min_final_pct": 80, "max_final_pct": 20}, headers=auth_header(hr)
    )
    assert r.status_code == 400


# ---------------------------------------------------------------- فیلتر/گزارش HR

def test_personnel_filters_and_sort(client, db_session):
    hr = make_user(db_session, "hr")
    # واحدهای یکتا تا با پرسنل seed تداخل نکند
    make_personnel(
        db_session, full_name="آ کارمند QA", org_unit="واحدQA-فروش", is_manager=False, status="active"
    )
    make_personnel(
        db_session, full_name="ی مدیر QA", org_unit="واحدQA-فناوری", is_manager=True, status="inactive"
    )
    db_session.commit()

    def names(**params):
        r = client.get("/api/personnel", params=params, headers=auth_header(hr))
        assert r.status_code == 200, r.text
        return [p["full_name"] for p in r.json()["items"]]

    assert names(org_unit="واحدQA-فروش") == ["آ کارمند QA"]
    assert names(org_unit="واحدQA-فناوری") == ["ی مدیر QA"]
    # فیلتر وضعیت + واحد یکتا با هم
    assert names(org_unit="واحدQA-فناوری", status="inactive") == ["ی مدیر QA"]
    assert names(org_unit="واحدQA-فناوری", status="active") == []
    # فیلتر مدیر + واحد یکتا
    assert names(org_unit="واحدQA-فناوری", is_manager=True) == ["ی مدیر QA"]
    assert names(org_unit="واحدQA-فروش", is_manager=True) == []
    # مرتب‌سازی نزولی بر اساس نام (هر دو نام QA با پیشوندهای متفاوت)
    desc = names(sort_by="full_name", sort_dir="desc")
    assert desc.index("ی مدیر QA") < desc.index("آ کارمند QA")


def test_personnel_export_respects_filters(client, db_session):
    hr = make_user(db_session, "hr")
    make_personnel(db_session, org_unit="واحد صادرات", status="active")
    db_session.commit()
    r = client.get(
        "/api/personnel/export.xlsx",
        params={"org_unit": "واحد صادرات", "status": "active"},
        headers=auth_header(hr),
    )
    assert r.status_code == 200
    assert r.content[:2] == b"PK"


def test_users_is_active_filter_and_export(client, db_session):
    hr = make_user(db_session, "hr")
    inactive = make_user(db_session, "deputy")
    inactive.is_active = False
    db_session.commit()

    active_ids = {
        u["id"] for u in client.get(
            "/api/users", params={"is_active": True}, headers=auth_header(hr)
        ).json()["items"]
    }
    assert inactive.id not in active_ids
    inactive_ids = {
        u["id"] for u in client.get(
            "/api/users", params={"is_active": False}, headers=auth_header(hr)
        ).json()["items"]
    }
    assert inactive.id in inactive_ids

    r = client.get("/api/users/export.xlsx", headers=auth_header(hr))
    assert r.status_code == 200
    assert r.content[:2] == b"PK"
    # فقط HR
    assert client.get("/api/users/export.xlsx", headers=auth_header(inactive)).status_code == 401


def test_audit_log_date_filter_and_export(client, db_session):
    hr = make_user(db_session, "hr")
    make_personnel(db_session)  # رویدادی نمی‌سازد اما جدول را پر می‌کند
    db_session.commit()
    # یک رویداد واقعی: ساخت کاربر
    client.post(
        "/api/users",
        json={"username": "newone", "password": "LongPass123", "role": "ceo"},
        headers=auth_header(hr),
    )

    today = date.today().isoformat()
    old = (date.today() - timedelta(days=10)).isoformat()
    r_today = client.get("/api/audit-log", params={"created_from": today}, headers=auth_header(hr))
    assert r_today.status_code == 200
    assert r_today.json()["total"] >= 1
    r_old = client.get("/api/audit-log", params={"created_to": old}, headers=auth_header(hr))
    assert r_old.status_code == 200

    r = client.get("/api/audit-log/export.xlsx", headers=auth_header(hr))
    assert r.status_code == 200
    assert r.content[:2] == b"PK"
