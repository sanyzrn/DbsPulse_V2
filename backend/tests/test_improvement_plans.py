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

    # از P1-10 به بعد، ارزیاب‌ها به این روتر دسترسی دارند ولی فقط به برنامه‌های
    # سپرده‌شده به خودشان. این مسئول واحد مالک هیچ برنامه‌ای نیست، پس فهرستش
    # خالی است — ادعایی قوی‌تر از ۴۰۳ قبلی: در را باز می‌کنیم و نشان می‌دهیم
    # پشتش چیزی برای این کاربر نیست.
    listed = client.get("/api/improvement-plans", headers=auth_header(sup))
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    # کارمند همچنان فقط از مسیر /api/me برنامهٔ خودش را می‌بیند
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


# ───────────────────────────── P1-10 · دسترسی مسئول پیگیری


def _plan_with_owner(client, db_session, owner):
    """یک برنامهٔ بهبود باز، با یک هدف، که به `owner` سپرده شده است."""
    personnel = make_personnel(db_session, full_name="نیازمند پیگیری")
    hr, sup, dep, ceo, evaluation_id = _finalize_with_conditional_result(
        client, db_session, personnel
    )
    plan = client.post(
        "/api/improvement-plans",
        json={
            "evaluation_record_id": evaluation_id,
            "title": "برنامهٔ بهبود کیفیت",
            "review_date": str(date.today() + timedelta(days=30)),
            "owner_user_id": owner.id,
        },
        headers=auth_header(hr),
    ).json()
    goal = client.post(
        f"/api/improvement-plans/{plan['id']}/goals",
        json={"description": "گذراندن دورهٔ کنترل کیفیت"},
        headers=auth_header(hr),
    ).json()
    return hr, plan, goal


def test_the_owner_can_open_the_plan_the_reminder_links_to(client, db_session):
    """قلب P1-10.

    زمان‌بند یادآوری بازنگری را به مسئول پیگیری می‌فرستد با لینک همین صفحه، ولی
    همهٔ endpointها `require_roles(hr)` بودند — یعنی سامانه از کسی کاری می‌خواست
    که اجازهٔ بازکردنش را به او نمی‌داد.
    """
    owner = make_user(db_session, "unit_supervisor")
    db_session.commit()
    _, plan, _ = _plan_with_owner(client, db_session, owner)

    r = client.get(f"/api/improvement-plans/{plan['id']}", headers=auth_header(owner))

    assert r.status_code == 200
    assert r.json()["title"] == "برنامهٔ بهبود کیفیت"


def test_the_owner_can_tick_a_goal_off(client, db_session):
    """کاری که اصلاً به او سپرده شده: پیگیری تحقق اهداف."""
    owner = make_user(db_session, "deputy")
    db_session.commit()
    _, plan, goal = _plan_with_owner(client, db_session, owner)

    r = client.patch(
        f"/api/improvement-plans/{plan['id']}/goals/{goal['id']}",
        json={"is_done": True},
        headers=auth_header(owner),
    )

    assert r.status_code == 200
    assert r.json()["is_done"] is True


def test_the_owner_may_not_rewrite_the_goal_text(client, db_session):
    """متن هدف را HR نوشته و مبنای تصمیم قرارداد است؛ اگر مجریِ برنامه بتواند
    بازنویسی‌اش کند، «هدف محقق شد» دیگر چیزی را ثابت نمی‌کند."""
    owner = make_user(db_session, "unit_supervisor")
    db_session.commit()
    _, plan, goal = _plan_with_owner(client, db_session, owner)

    r = client.patch(
        f"/api/improvement-plans/{plan['id']}/goals/{goal['id']}",
        json={"description": "یک هدف آسان‌تر"},
        headers=auth_header(owner),
    )

    assert r.status_code == 403


def test_the_owner_may_not_complete_or_cancel_the_plan(client, db_session):
    owner = make_user(db_session, "unit_supervisor")
    db_session.commit()
    _, plan, _ = _plan_with_owner(client, db_session, owner)

    assert (
        client.post(
            f"/api/improvement-plans/{plan['id']}/complete", headers=auth_header(owner)
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/improvement-plans/{plan['id']}/cancel", headers=auth_header(owner)
        ).status_code
        == 403
    )


def test_the_owner_may_not_add_or_delete_goals(client, db_session):
    owner = make_user(db_session, "unit_supervisor")
    db_session.commit()
    _, plan, goal = _plan_with_owner(client, db_session, owner)

    assert (
        client.post(
            f"/api/improvement-plans/{plan['id']}/goals",
            json={"description": "هدف خودساخته"},
            headers=auth_header(owner),
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/improvement-plans/{plan['id']}/goals/{goal['id']}",
            headers=auth_header(owner),
        ).status_code
        == 403
    )


def test_someone_elses_plan_stays_closed(client, db_session):
    """گشودن دسترسی نباید به «هر ارزیابی می‌تواند هر برنامه‌ای را ببیند» تبدیل شود."""
    owner = make_user(db_session, "unit_supervisor")
    stranger = make_user(db_session, "deputy")
    db_session.commit()
    _, plan, goal = _plan_with_owner(client, db_session, owner)

    assert (
        client.get(
            f"/api/improvement-plans/{plan['id']}", headers=auth_header(stranger)
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/improvement-plans/{plan['id']}/goals/{goal['id']}",
            json={"is_done": True},
            headers=auth_header(stranger),
        ).status_code
        == 403
    )


def test_the_list_shows_the_owner_only_their_own_plans(client, db_session):
    owner = make_user(db_session, "unit_supervisor")
    stranger = make_user(db_session, "deputy")
    db_session.commit()
    hr, plan, _ = _plan_with_owner(client, db_session, owner)

    mine = client.get("/api/improvement-plans", headers=auth_header(owner)).json()
    assert [p["id"] for p in mine["items"]] == [plan["id"]]

    theirs = client.get("/api/improvement-plans", headers=auth_header(stranger)).json()
    assert theirs["items"] == []

    # HR همچنان همه را می‌بیند
    all_plans = client.get("/api/improvement-plans", headers=auth_header(hr)).json()
    assert any(p["id"] == plan["id"] for p in all_plans["items"])


def test_an_employee_cannot_reach_improvement_plans(client, db_session):
    """کارمند برنامهٔ خودش را از مسیر /api/me می‌بیند، نه از این مسیر."""
    employee = make_user(db_session, "employee")
    owner = make_user(db_session, "unit_supervisor")
    db_session.commit()
    _, plan, _ = _plan_with_owner(client, db_session, owner)

    assert (
        client.get(
            f"/api/improvement-plans/{plan['id']}", headers=auth_header(employee)
        ).status_code
        == 403
    )


# ── واجد بودن، با عدد نه با برچسب ───────────────────────────────────────────
#
# ممیزی HR ایراد گرفت که واجد بودن فقط یک برچسب را می‌پذیرد: «تمدید مشروط».
# یعنی نتایج زیر ۶۰٪ — بدترین عملکردها، همان‌هایی که پیش از قطع همکاری بیشتر از
# همه به سابقهٔ مکتوب نیاز دارند — هیچ مسیر مستندسازی نداشتند.

def _finalize_with_score(client, db, personnel, score: int) -> dict:
    """یک پروندهٔ نهایی‌شده با امتیازِ دلخواه روی همهٔ شاخص‌ها."""
    from tests.helpers import active_indicators, full_valid_scores, make_access, make_user

    hr = make_user(db, "hr")
    sup = make_user(db, "unit_supervisor")
    dep = make_user(db, "deputy")
    ceo = make_user(db, "ceo", capabilities=[])
    make_access(db, personnel, sup, dep, ceo)
    db.commit()

    record_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": personnel.id},
        headers=auth_header(sup),
    ).json()["id"]
    # نمرهٔ ۱ شواهد اجباری دارد، پس همیشه همراهش می‌آید.
    rows = [
        {**row, "score": score, "evidence_text": "شواهد کافی برای این شاخص ثبت شده است"}
        for row in full_valid_scores(active_indicators(db))
    ]
    client.put(
        f"/api/evaluations/{record_id}/scores", json={"scores": rows}, headers=auth_header(sup)
    )
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(sup))
    client.post(f"/api/evaluations/{record_id}/hr-approve", headers=auth_header(hr))
    client.post(f"/api/evaluations/{record_id}/deputy-approve", headers=auth_header(dep))
    client.post(f"/api/evaluations/{record_id}/ceo-finalize", headers=auth_header(ceo))
    return {"record_id": record_id, "hr": hr}


def test_a_sub_sixty_result_is_now_eligible_for_a_plan(client, db_session):
    """پیش از این، «عدم تمدید» هیچ برنامهٔ بهبودی نمی‌گرفت — معکوسِ چیزی که باید."""
    personnel = make_personnel(db_session, full_name="نتیجهٔ بسیار پایین")
    context = _finalize_with_score(client, db_session, personnel, score=1)

    eligible = client.get(
        "/api/improvement-plans/eligible", headers=auth_header(context["hr"])
    ).json()
    codes = {row["evaluation_record_id"] for row in eligible}
    assert context["record_id"] in codes

    created = client.post(
        "/api/improvement-plans",
        json={
            "evaluation_record_id": context["record_id"],
            "title": "برنامهٔ بهبود پس از نتیجهٔ بسیار پایین",
            "owner_user_id": context["hr"].id,
            "review_date": "2026-12-01",
            "summary": "سه هدف مشخص با بازبینی ماهانه",
        },
        headers=auth_header(context["hr"]),
    )
    assert created.status_code == 201, created.text


def test_a_good_result_is_still_not_eligible(client, db_session):
    """سقف باید سقف بماند؛ وگرنه «واجد بودن» هیچ معنایی ندارد."""
    personnel = make_personnel(db_session, full_name="نتیجهٔ خوب")
    context = _finalize_with_score(client, db_session, personnel, score=5)

    eligible = client.get(
        "/api/improvement-plans/eligible", headers=auth_header(context["hr"])
    ).json()
    assert context["record_id"] not in {row["evaluation_record_id"] for row in eligible}

    refused = client.post(
        "/api/improvement-plans",
        json={
            "evaluation_record_id": context["record_id"],
            "title": "برنامهٔ بی‌مورد",
            "owner_user_id": context["hr"].id,
            "review_date": "2026-12-01",
            "summary": "—",
        },
        headers=auth_header(context["hr"]),
    )
    assert refused.status_code == 400, refused.text
