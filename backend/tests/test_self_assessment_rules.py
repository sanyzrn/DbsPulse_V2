"""قاعده‌هایی که منابع انسانی برای خودارزیابی تعیین کرد.

سه چیز این‌جا قفل می‌شود، و هر سه از آن‌هایی‌اند که اگر بشکنند بی‌صدا می‌شکنند:

۱. **چه کسی خودارزیابی دارد** — همه، به‌جز مدیرعامل و معاونت‌ها. قاعده
   زنجیره‌محور است نه نقش‌محور: مسئولِ واحد هم‌زمان ارزیاب و ارزیابی‌شونده است.

۲. **مهلتِ ثبت واقعی است** — پس از پایانِ دوره نه خودارزیابی ثبت می‌شود و نه
   نمرهٔ ارزیاب. ستون‌های `starts_on`/`ends_on` سال‌ها بود که فقط یک برچسب بودند.

۳. **تمدید، استثنایی تاریخ‌دار است** — منابع انسانی برای یک پروندهٔ مشخص باز
   می‌کند، و همان تاریخ خودش دوباره می‌بندد.
"""
from datetime import date, timedelta

from app.models.enums import Capability, PeriodStatus
from app.models.evaluation import EvaluationRecord
from app.models.evaluation_period import EvaluationPeriod
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


def _open_case(client, db_session, *, subject_role: str = "employee", period_ends: date | None = None):
    """یک پروندهٔ باز، با نقشِ دلخواه برای *خودِ فرد*.

    `subject_role` همان چیزی است که تست‌های واجد بودن به آن نیاز دارند: مسئولِ
    واحدی که خودش ارزیابی می‌شود، معاونتی که نباید خودارزیابی داشته باشد.
    """
    hr = make_user(db_session, "hr", capabilities=[Capability.view_audit_log])
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session, full_name="فردِ ارزیابی‌شونده")
    subject = make_user(db_session, subject_role, personnel_id=personnel.id)
    make_access(db_session, personnel, sup, dep, ceo)

    period = None
    if period_ends is not None:
        period = EvaluationPeriod(
            name="دورهٔ آزمایشی",
            starts_on=period_ends - timedelta(days=30),
            ends_on=period_ends,
            # `closed` تا ایندکسِ «حداکثر یک دورهٔ باز» با تست‌های موازی درنیفتد؛
            # مهلت از خودِ تاریخ می‌آید، نه از وضعیتِ دوره.
            status=PeriodStatus.closed,
        )
        db_session.add(period)
        db_session.flush()
    db_session.commit()

    created = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    ).json()
    if period is not None:
        record = db_session.get(EvaluationRecord, created["id"])
        record.period_id = period.id
        db_session.commit()

    return {
        "id": created["id"], "hr": hr, "sup": sup, "dep": dep, "ceo": ceo,
        "subject": subject, "personnel": personnel, "period": period,
    }


def _payload(db_session, score: int) -> dict:
    return {
        "scores": [{"indicator_id": i.id, "score": score} for i in active_indicators(db_session)],
        "note": None,
    }


# ── چه کسی خودارزیابی دارد ──────────────────────────────────────────────

def test_a_unit_supervisor_can_self_assess_their_own_case(client, db_session):
    """همان اشکالی که این تغییر برایش شروع شد.

    گاردِ مسیرها `require_roles(employee)` بود — تطابقِ دقیقِ نقش. مسئولِ واحد که
    خودش هم ارزیابی می‌شود، روی *همهٔ* مسیرهای `/api/me` ۴۰۳ می‌گرفت.
    """
    case = _open_case(client, db_session, subject_role="unit_supervisor")

    response = client.post(
        f"/api/me/evaluations/{case['id']}/self-assessment",
        json=_payload(db_session, 4),
        headers=auth_header(case["subject"]),
    )

    assert response.status_code == 200, response.text
    assert response.json()["submitted_at"] is not None


def test_a_unit_supervisor_can_reach_their_own_scorecard(client, db_session):
    # همان ریشه، شاخهٔ دوم: نه‌تنها خودارزیابی، نتیجهٔ خودش را هم نمی‌دید.
    case = _open_case(client, db_session, subject_role="unit_supervisor")
    assert client.get("/api/me/evaluations", headers=auth_header(case["subject"])).status_code == 200
    assert client.get("/api/me/evaluations/open", headers=auth_header(case["subject"])).status_code == 200


def test_a_deputy_has_no_self_assessment(client, db_session):
    case = _open_case(client, db_session, subject_role="deputy")

    response = client.post(
        f"/api/me/evaluations/{case['id']}/self-assessment",
        json=_payload(db_session, 4),
        headers=auth_header(case["subject"]),
    )

    assert response.status_code == 403
    assert "خودارزیابی" in response.json()["detail"]


def test_a_deputy_still_sees_their_own_scorecard(client, db_session):
    # استثنا فقط دربارهٔ *ثبتِ* خودارزیابی است. دیدنِ نتیجهٔ خود، حقِ همه است.
    case = _open_case(client, db_session, subject_role="deputy")
    assert client.get("/api/me/evaluations", headers=auth_header(case["subject"])).status_code == 200


def test_the_open_case_view_says_self_assessment_is_closed_for_a_deputy(client, db_session):
    """رابط نباید فرمی را نشان بدهد که سرور ردش می‌کند."""
    case = _open_case(client, db_session, subject_role="deputy")
    rows = client.get("/api/me/evaluations/open", headers=auth_header(case["subject"])).json()
    assert rows and rows[0]["self_assessment_open"] is False


def test_an_account_without_personnel_is_told_why(client, db_session):
    stranger = make_user(db_session, "hr")
    db_session.commit()
    response = client.get("/api/me/evaluations", headers=auth_header(stranger))
    assert response.status_code == 403
    assert "پروندهٔ پرسنلی" in response.json()["detail"]


# ── مهلتِ ثبت ───────────────────────────────────────────────────────────

def test_self_assessment_is_refused_after_the_period_ended(client, db_session):
    case = _open_case(client, db_session, period_ends=date.today() - timedelta(days=1))

    response = client.post(
        f"/api/me/evaluations/{case['id']}/self-assessment",
        json=_payload(db_session, 3),
        headers=auth_header(case["subject"]),
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    # پیام باید *تاریخ* را بگوید: «مهلت گذشته» بی‌تاریخ، به کاربر نمی‌گوید چقدر
    # دیر کرده یا اصلاً مهلت کِی بوده.
    assert str(case["period"].ends_on.year) in detail
    assert "تمدید" in detail


def test_the_evaluator_cannot_submit_scores_after_the_period_ended(client, db_session):
    """مهلت برای «ارزیابی تیم» هم هست، نه فقط خودارزیابی."""
    case = _open_case(client, db_session, period_ends=date.today() - timedelta(days=1))
    client.put(
        f"/api/evaluations/{case['id']}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(case["sup"]),
    )

    response = client.post(f"/api/evaluations/{case['id']}/submit", headers=auth_header(case["sup"]))

    assert response.status_code == 400
    assert "مهلت ثبت ارزیابی" in response.json()["detail"]


def test_a_period_that_is_still_running_blocks_nothing(client, db_session):
    case = _open_case(client, db_session, period_ends=date.today() + timedelta(days=7))
    response = client.post(
        f"/api/me/evaluations/{case['id']}/self-assessment",
        json=_payload(db_session, 3),
        headers=auth_header(case["subject"]),
    )
    assert response.status_code == 200, response.text


def test_a_case_with_no_period_has_no_deadline(client, db_session):
    """پرونده‌های پیش از معرفیِ دوره‌ها نباید یک‌شبه غیرقابل‌ثبت شوند.

    `period_id` این‌جا صریحاً پاک می‌شود و به نبودِ دورهٔ باز تکیه نمی‌شود: در این
    مجموعه یک fixture خودکار همیشه یک دورهٔ باز می‌سازد، پس پروندهٔ تازه همیشه
    برچسب می‌خورد. تکیه به آن یعنی تست چیزی را می‌سنجد که فکر می‌کنیم می‌سنجد.
    """
    case = _open_case(client, db_session)
    record = db_session.get(EvaluationRecord, case["id"])
    record.period_id = None
    db_session.commit()

    rows = client.get("/api/me/evaluations/open", headers=auth_header(case["subject"])).json()
    assert rows[0]["submission_deadline"] is None
    assert rows[0]["self_assessment_open"] is True


# ── تمدید ───────────────────────────────────────────────────────────────

def test_hr_can_reopen_one_case_after_the_deadline(client, db_session):
    case = _open_case(client, db_session, period_ends=date.today() - timedelta(days=2))
    new_deadline = date.today() + timedelta(days=3)

    extended = client.post(
        f"/api/evaluations/{case['id']}/extend-submission",
        json={"until": new_deadline.isoformat(), "reason": "فرد در مرخصی استعلاجی بود"},
        headers=auth_header(case["hr"]),
    )
    assert extended.status_code == 200, extended.text
    assert extended.json()["submission_deadline"] == new_deadline.isoformat()
    assert extended.json()["submission_deadline_extended"] is True

    # و حالا همان ثبتی که رد می‌شد، می‌گیرد.
    response = client.post(
        f"/api/me/evaluations/{case['id']}/self-assessment",
        json=_payload(db_session, 5),
        headers=auth_header(case["subject"]),
    )
    assert response.status_code == 200, response.text


def test_an_extension_earlier_than_the_period_end_never_shortens_it(client, db_session):
    """«باز کردنِ دوباره» هیچ‌وقت نباید چیزی را ببندد."""
    period_end = date.today() + timedelta(days=10)
    case = _open_case(client, db_session, period_ends=period_end)

    client.post(
        f"/api/evaluations/{case['id']}/extend-submission",
        json={"until": (date.today() - timedelta(days=1)).isoformat(), "reason": "اشتباهِ تایپی"},
        headers=auth_header(case["hr"]),
    )

    rows = client.get("/api/me/evaluations/open", headers=auth_header(case["subject"])).json()
    assert rows[0]["submission_deadline"] == period_end.isoformat()
    assert rows[0]["self_assessment_open"] is True


def test_an_extension_needs_a_reason(client, db_session):
    case = _open_case(client, db_session, period_ends=date.today() - timedelta(days=1))
    response = client.post(
        f"/api/evaluations/{case['id']}/extend-submission",
        json={"until": date.today().isoformat(), "reason": ""},
        headers=auth_header(case["hr"]),
    )
    assert response.status_code == 422


def test_only_hr_can_extend(client, db_session):
    case = _open_case(client, db_session, period_ends=date.today() - timedelta(days=1))
    response = client.post(
        f"/api/evaluations/{case['id']}/extend-submission",
        json={"until": date.today().isoformat(), "reason": "تلاش برای تمدیدِ خودی"},
        headers=auth_header(case["sup"]),
    )
    assert response.status_code == 403


def test_extending_a_case_that_is_past_the_scoring_stage_is_refused(client, db_session):
    """تمدید برای پرونده‌ای که از مرحلهٔ ثبت گذشته، چیزی را باز نمی‌کند."""
    case = _open_case(client, db_session)
    client.put(
        f"/api/evaluations/{case['id']}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(case["sup"]),
    )
    client.post(f"/api/evaluations/{case['id']}/submit", headers=auth_header(case["sup"]))

    response = client.post(
        f"/api/evaluations/{case['id']}/extend-submission",
        json={"until": (date.today() + timedelta(days=5)).isoformat(), "reason": "دیر شد"},
        headers=auth_header(case["hr"]),
    )
    assert response.status_code == 400
