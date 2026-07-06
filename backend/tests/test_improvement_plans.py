"""تست‌های برنامه بهبود (R13.2): ساخت مشروط به نتیجه، اهداف، تکمیل، یادآوری بازنگری."""
from datetime import date, timedelta

from sqlalchemy import select

from app.core.constants import FINAL_RESULT_THRESHOLDS
from app.models.improvement_plan import ImprovementPlan
from app.models.notification import Notification
from app.services.scheduled import run_improvement_review_sweep
from tests.helpers import (
    active_indicators,
    auth_header,
    make_access,
    make_personnel,
    make_user,
)

# نتیجه‌ای که برنامه بهبود را ایجاب می‌کند: بازه [60, 75) → همه امتیاز ۳ (۶۰٪)
CONDITIONAL_LABEL = FINAL_RESULT_THRESHOLDS[1][1]


def _finalize_with_conditional_result(client, db, personnel):
    """پرونده‌ای می‌سازد و تا نهایی‌شدن پیش می‌برد؛ همه امتیاز ۳ → ۶۰٪ → «تمدید مشروط»."""
    hr = make_user(db, "hr")
    sup = make_user(db, "unit_supervisor")
    dep = make_user(db, "deputy")
    ceo = make_user(db, "ceo")
    make_access(db, personnel, sup, dep, ceo)
    db.commit()

    indicators = active_indicators(db)
    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    )
    evaluation_id = r.json()["id"]
    client.put(
        f"/api/evaluations/{evaluation_id}/scores",
        json={"scores": [{"indicator_id": i.id, "score": 3} for i in indicators]},
        headers=auth_header(sup),
    )
    client.post(f"/api/evaluations/{evaluation_id}/submit", headers=auth_header(sup))
    client.post(f"/api/evaluations/{evaluation_id}/hr-approve", headers=auth_header(hr))
    client.post(f"/api/evaluations/{evaluation_id}/deputy-approve", headers=auth_header(dep))
    final = client.post(f"/api/evaluations/{evaluation_id}/ceo-finalize", headers=auth_header(ceo))
    assert final.json()["recommendation"] == CONDITIONAL_LABEL, final.text
    return hr, sup, dep, ceo, evaluation_id


def test_eligible_lists_only_conditional_without_plan(client, db_session):
    personnel = make_personnel(db_session, full_name="نیازمند بهبود")
    hr, sup, dep, ceo, evaluation_id = _finalize_with_conditional_result(client, db_session, personnel)

    r = client.get("/api/improvement-plans/eligible", headers=auth_header(hr))
    assert r.status_code == 200
    assert any(item["evaluation_record_id"] == evaluation_id for item in r.json())

    # پس از ساخت برنامه، دیگر در فهرست eligible نیست
    created = client.post(
        "/api/improvement-plans",
        json={
            "evaluation_record_id": evaluation_id,
            "title": "برنامه بهبود سه‌ماهه",
            "review_date": (date.today() + timedelta(days=30)).isoformat(),
            "goals": ["بهبود مهارت گزارش‌نویسی", "شرکت در دوره آموزشی"],
        },
        headers=auth_header(hr),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert len(body["goals"]) == 2
    assert body["status"] == "open"

    r = client.get("/api/improvement-plans/eligible", headers=auth_header(hr))
    assert all(item["evaluation_record_id"] != evaluation_id for item in r.json())


def test_plan_rejected_for_non_conditional_result(client, db_session):
    """ارزیابی با امتیاز کامل (۱۰۰٪ → ارتقاء) نباید برنامه بهبود بپذیرد."""
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session, full_name="عملکرد عالی")
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    indicators = active_indicators(db_session)
    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    )
    evaluation_id = r.json()["id"]
    client.put(
        f"/api/evaluations/{evaluation_id}/scores",
        json={"scores": [{"indicator_id": i.id, "score": 5} for i in indicators]},
        headers=auth_header(sup),
    )
    client.post(f"/api/evaluations/{evaluation_id}/submit", headers=auth_header(sup))
    client.post(f"/api/evaluations/{evaluation_id}/hr-approve", headers=auth_header(hr))
    client.post(f"/api/evaluations/{evaluation_id}/deputy-approve", headers=auth_header(dep))
    client.post(f"/api/evaluations/{evaluation_id}/ceo-finalize", headers=auth_header(ceo))

    r = client.post(
        "/api/improvement-plans",
        json={
            "evaluation_record_id": evaluation_id,
            "title": "بی‌مورد",
            "review_date": (date.today() + timedelta(days=30)).isoformat(),
        },
        headers=auth_header(hr),
    )
    assert r.status_code == 400


def test_one_plan_per_evaluation(client, db_session):
    personnel = make_personnel(db_session)
    hr, sup, dep, ceo, evaluation_id = _finalize_with_conditional_result(client, db_session, personnel)
    payload = {
        "evaluation_record_id": evaluation_id,
        "title": "اول",
        "review_date": (date.today() + timedelta(days=30)).isoformat(),
    }
    assert client.post("/api/improvement-plans", json=payload, headers=auth_header(hr)).status_code == 201
    dup = client.post("/api/improvement-plans", json=payload, headers=auth_header(hr))
    assert dup.status_code == 409


def test_goal_lifecycle_and_completion(client, db_session):
    personnel = make_personnel(db_session)
    hr, sup, dep, ceo, evaluation_id = _finalize_with_conditional_result(client, db_session, personnel)
    plan = client.post(
        "/api/improvement-plans",
        json={
            "evaluation_record_id": evaluation_id,
            "title": "برنامه",
            "review_date": (date.today() + timedelta(days=10)).isoformat(),
            "goals": ["هدف اول"],
        },
        headers=auth_header(hr),
    ).json()
    plan_id = plan["id"]
    first_goal_id = plan["goals"][0]["id"]

    # افزودن هدف
    g2 = client.post(
        f"/api/improvement-plans/{plan_id}/goals",
        json={"description": "هدف دوم"},
        headers=auth_header(hr),
    )
    assert g2.status_code == 201
    assert g2.json()["display_order"] == 1

    # علامت انجام‌شده
    upd = client.patch(
        f"/api/improvement-plans/{plan_id}/goals/{first_goal_id}",
        json={"is_done": True},
        headers=auth_header(hr),
    )
    assert upd.status_code == 200 and upd.json()["is_done"] is True

    # حذف هدف دوم
    assert client.delete(
        f"/api/improvement-plans/{plan_id}/goals/{g2.json()['id']}", headers=auth_header(hr)
    ).status_code == 204

    detail = client.get(f"/api/improvement-plans/{plan_id}", headers=auth_header(hr))
    assert len(detail.json()["goals"]) == 1

    # تکمیل برنامه
    done = client.post(f"/api/improvement-plans/{plan_id}/complete", headers=auth_header(hr))
    assert done.status_code == 200 and done.json()["status"] == "completed"
    assert done.json()["completed_at"] is not None
    # تکمیل دوباره ممنوع
    assert client.post(
        f"/api/improvement-plans/{plan_id}/complete", headers=auth_header(hr)
    ).status_code == 400


def test_owner_assignment_notifies_and_validates(client, db_session):
    personnel = make_personnel(db_session)
    hr, sup, dep, ceo, evaluation_id = _finalize_with_conditional_result(client, db_session, personnel)

    # owner نامعتبر رد می‌شود
    bad = client.post(
        "/api/improvement-plans",
        json={
            "evaluation_record_id": evaluation_id,
            "title": "با مسئول نامعتبر",
            "review_date": (date.today() + timedelta(days=30)).isoformat(),
            "owner_user_id": 999999,
        },
        headers=auth_header(hr),
    )
    assert bad.status_code == 400

    ok = client.post(
        "/api/improvement-plans",
        json={
            "evaluation_record_id": evaluation_id,
            "title": "با مسئول معتبر",
            "review_date": (date.today() + timedelta(days=30)).isoformat(),
            "owner_user_id": sup.id,
        },
        headers=auth_header(hr),
    )
    assert ok.status_code == 201
    notes = list(
        db_session.scalars(
            select(Notification).where(
                Notification.user_id == sup.id,
                Notification.type == "improvement_plan_assigned",
            )
        )
    )
    assert len(notes) == 1


def test_owner_assigned_via_patch_notifies(client, db_session):
    personnel = make_personnel(db_session)
    hr, sup, dep, ceo, evaluation_id = _finalize_with_conditional_result(client, db_session, personnel)
    plan = client.post(
        "/api/improvement-plans",
        json={
            "evaluation_record_id": evaluation_id,
            "title": "بدون مسئول اولیه",
            "review_date": (date.today() + timedelta(days=30)).isoformat(),
        },
        headers=auth_header(hr),
    ).json()

    r = client.patch(
        f"/api/improvement-plans/{plan['id']}",
        json={"owner_user_id": sup.id},
        headers=auth_header(hr),
    )
    assert r.status_code == 200 and r.json()["owner_user_id"] == sup.id
    notes = list(
        db_session.scalars(
            select(Notification).where(
                Notification.user_id == sup.id,
                Notification.type == "improvement_plan_assigned",
            )
        )
    )
    assert len(notes) == 1


def test_review_sweep_reminds_when_due(client, db_session):
    personnel = make_personnel(db_session, full_name="بازنگری نزدیک")
    hr, sup, dep, ceo, evaluation_id = _finalize_with_conditional_result(client, db_session, personnel)
    client.post(
        "/api/improvement-plans",
        json={
            "evaluation_record_id": evaluation_id,
            "title": "برنامه رو به بازنگری",
            "review_date": (date.today() + timedelta(days=2)).isoformat(),
            "owner_user_id": sup.id,
        },
        headers=auth_header(hr),
    )

    created = run_improvement_review_sweep(db_session)
    db_session.commit()
    assert created >= 2  # حداقل HR و مسئول پیگیری

    owner_notes = list(
        db_session.scalars(
            select(Notification).where(
                Notification.user_id == sup.id, Notification.type == "improvement_review_due"
            )
        )
    )
    assert len(owner_notes) == 1

    # اجرای دوباره در پنجره dedup تکرار نمی‌کند
    assert run_improvement_review_sweep(db_session) == 0


def test_employee_sees_own_open_plan(client, db_session):
    personnel = make_personnel(db_session, full_name="کارمند دارای برنامه")
    hr, sup, dep, ceo, evaluation_id = _finalize_with_conditional_result(client, db_session, personnel)
    employee = make_user(db_session, "employee", personnel_id=personnel.id)
    db_session.commit()

    client.post(
        "/api/improvement-plans",
        json={
            "evaluation_record_id": evaluation_id,
            "title": "برنامه من",
            "review_date": (date.today() + timedelta(days=30)).isoformat(),
            "goals": ["هدف قابل مشاهده"],
        },
        headers=auth_header(hr),
    )

    r = client.get("/api/me/improvement-plans", headers=auth_header(employee))
    assert r.status_code == 200
    plans = r.json()
    assert len(plans) == 1
    assert plans[0]["goals"][0]["description"] == "هدف قابل مشاهده"

    # نقش‌های دیگر به روتر مدیریتی برنامه دسترسی ندارند
    assert client.get("/api/improvement-plans", headers=auth_header(sup)).status_code == 403
    assert client.get("/api/improvement-plans", headers=auth_header(employee)).status_code == 403


def test_plan_persisted_with_evaluation_link(client, db_session):
    personnel = make_personnel(db_session)
    hr, sup, dep, ceo, evaluation_id = _finalize_with_conditional_result(client, db_session, personnel)
    client.post(
        "/api/improvement-plans",
        json={
            "evaluation_record_id": evaluation_id,
            "title": "پیوند",
            "review_date": (date.today() + timedelta(days=30)).isoformat(),
        },
        headers=auth_header(hr),
    )
    plan = db_session.scalar(
        select(ImprovementPlan).where(ImprovementPlan.evaluation_record_id == evaluation_id)
    )
    assert plan is not None
    assert plan.personnel_id == personnel.id
