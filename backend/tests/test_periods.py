"""تست‌های دوره‌های (کمپین) ارزیابی: تک‌دوره باز، برچسب خودکار، پیشرفت و بستن."""
from datetime import date, timedelta

from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


def _create_period(client, hr, name="دوره آزمون") -> dict:
    today = date.today()
    r = client.post(
        "/api/periods",
        json={
            "name": name,
            "starts_on": str(today - timedelta(days=30)),
            "ends_on": str(today + timedelta(days=30)),
        },
        headers=auth_header(hr),
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_only_one_open_period_at_a_time(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()

    period = _create_period(client, hr)
    assert period["status"] == "open"

    r = client.post(
        "/api/periods",
        json={"name": "دوره دوم", "starts_on": "2026-10-01", "ends_on": "2026-12-30"},
        headers=auth_header(hr),
    )
    assert r.status_code == 400
    assert "هنوز باز است" in r.json()["detail"]

    # بعد از بستن، دوره جدید مجاز است
    r = client.post(f"/api/periods/{period['id']}/close", headers=auth_header(hr))
    assert r.status_code == 200
    assert r.json()["status"] == "closed"
    assert r.json()["closed_at"] is not None

    r = client.post(
        "/api/periods",
        json={"name": "دوره دوم", "starts_on": "2026-10-01", "ends_on": "2026-12-30"},
        headers=auth_header(hr),
    )
    assert r.status_code == 201


def test_period_dates_must_be_in_order(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()
    r = client.post(
        "/api/periods",
        json={"name": "برعکس", "starts_on": "2026-09-30", "ends_on": "2026-07-01"},
        headers=auth_header(hr),
    )
    assert r.status_code == 422


def test_new_evaluations_are_tagged_with_open_period(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    period = _create_period(client, hr)

    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    )
    assert r.status_code == 201
    assert r.json()["period_id"] == period["id"]


def test_an_evaluation_without_an_open_period_is_created_without_a_deadline(client, db_session):
    """نبودِ دورهٔ باز، ساختِ پرونده را متوقف نمی‌کند.

    شرطِ «دورهٔ باز لازم است» دو چیز را می‌شکند: سازمانی که ماژول دوره‌ها را
    به‌کار نمی‌گیرد اصلاً نمی‌تواند ارزیابی کند، و در فاصلهٔ بستنِ یک دوره تا
    باز کردنِ دورهٔ بعد هیچ پرونده‌ای باز نمی‌شود.

    پروندهٔ بی‌دوره مهلتی هم ندارد — قاعده‌اش در `services/evaluation_window.py`
    است و همان‌جا تست می‌شود.
    """
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    )

    assert r.status_code == 201, r.text
    assert r.json()["period_id"] is None
    assert r.json()["submission_deadline"] is None


def test_moving_the_period_end_closes_and_reopens_score_entry(client, db_session):
    """مهلت روی *ثبت* می‌نشیند، نه روی ساختِ پرونده.

    بستنِ ساختِ پرونده چیزی را نجات نمی‌دهد و یک بن‌بست می‌سازد: پرونده‌ای که
    باز نشده، بعداً هم نمی‌شود بازش کرد. آن‌چه باید بسته شود ثبتِ نمره است، و
    همان است که این‌جا با جابه‌جایی `ends_on` بسته و دوباره باز می‌شود.

    تمدیدِ *یک پرونده* راهِ دیگری دارد (`POST /evaluations/{id}/extend-submission`)
    که در test_self_assessment_rules.py تست می‌شود؛ عقب انداختنِ `ends_on` در را
    برای همه باز می‌کند و این تست همان را می‌سنجد.
    """
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()
    _create_period(client, hr)
    today = date.today()

    created = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": personnel.id},
        headers=auth_header(sup),
    )
    assert created.status_code == 201, created.text
    evaluation_id = created.json()["id"]
    period_id = created.json()["period_id"]
    assert period_id is not None, "پروندهٔ تازه باید به دورهٔ باز بچسبد"

    client.put(
        f"/api/evaluations/{evaluation_id}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(sup),
    )

    expired = client.patch(
        f"/api/periods/{period_id}",
        json={
            "starts_on": str(today - timedelta(days=10)),
            "ends_on": str(today - timedelta(days=1)),
        },
        headers=auth_header(hr),
    )
    assert expired.status_code == 200
    assert expired.json()["window_state"] == "expired"

    blocked = client.post(
        f"/api/evaluations/{evaluation_id}/submit", headers=auth_header(sup)
    )
    assert blocked.status_code == 400
    assert "مهلت ثبت" in blocked.json()["detail"]

    extended = client.patch(
        f"/api/periods/{period_id}",
        json={"ends_on": str(today + timedelta(days=10))},
        headers=auth_header(hr),
    )
    assert extended.status_code == 200
    assert extended.json()["accepting_entries"] is True

    restored = client.post(
        f"/api/evaluations/{evaluation_id}/submit", headers=auth_header(sup)
    )
    assert restored.status_code == 200, restored.text


def test_period_progress_tracks_cohort(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    p1 = make_personnel(db_session, full_name="عضو دوره یک")
    p2 = make_personnel(db_session, full_name="عضو دوره دو")
    make_access(db_session, p1, sup, dep, ceo)
    make_access(db_session, p2, sup, dep, ceo)
    db_session.commit()

    period = _create_period(client, hr)

    r = client.get(f"/api/periods/{period['id']}/progress", headers=auth_header(hr))
    assert r.status_code == 200
    body = r.json()
    # دیتابیس تست seed هم دارد؛ فقط نسبت به دو نفرِ همین تست قضاوت می‌کنیم
    assert body["eligible"] >= 2
    assert body["started"] == 0
    names = [x["full_name"] for x in body["not_started"]]
    assert "عضو دوره یک" in names and "عضو دوره دو" in names

    # با شروع ارزیابی یک نفر، از فهرست جامانده‌ها خارج می‌شود
    client.post("/api/evaluations", json={"subject_personnel_id": p1.id}, headers=auth_header(sup))
    r = client.get(f"/api/periods/{period['id']}/progress", headers=auth_header(hr))
    body = r.json()
    assert body["started"] == 1
    assert body["finalized"] == 0
    names = [x["full_name"] for x in body["not_started"]]
    assert "عضو دوره یک" not in names and "عضو دوره دو" in names


def test_opening_period_notifies_evaluators(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    db_session.commit()

    _create_period(client, hr, name="دوره اطلاع‌رسانی")

    r = client.get("/api/notifications", headers=auth_header(sup))
    assert any("دوره ارزیابی «دوره اطلاع‌رسانی» آغاز شد" in n["message"] for n in r.json()["items"])


def test_periods_are_hr_only(client, db_session):
    sup = make_user(db_session, "unit_supervisor")
    db_session.commit()
    assert client.get("/api/periods", headers=auth_header(sup)).status_code == 403
    r = client.post(
        "/api/periods",
        json={"name": "x", "starts_on": "2026-07-01", "ends_on": "2026-09-30"},
        headers=auth_header(sup),
    )
    assert r.status_code == 403


def test_progress_reports_how_many_files_are_still_mid_workflow(client, db_session):
    """عددی که تصمیمِ بستن دوره به آن بستگی دارد.

    بستن دوره‌ای که چند پرونده وسط گردش‌کار دارد اشتباهی است که باید *پیش* از
    انجامش دیده شود؛ تا پیش از این هیچ‌جا شمرده نمی‌شد.
    """
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    person = make_personnel(db_session, full_name="پروندهٔ باز")
    make_access(db_session, person, sup, dep, ceo)
    db_session.commit()

    period = _create_period(client, hr)
    progress = lambda: client.get(  # noqa: E731
        f"/api/periods/{period['id']}/progress", headers=auth_header(hr)
    ).json()

    assert progress()["in_progress"] == 0

    client.post(
        "/api/evaluations", json={"subject_personnel_id": person.id}, headers=auth_header(sup)
    )
    assert progress()["in_progress"] == 1


def test_a_cancelled_file_counts_as_neither_open_nor_finalized(client, db_session):
    """«started منهای finalized» غلط بود: پروندهٔ لغوشده را «در جریان» نشان می‌داد."""
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    person = make_personnel(db_session, full_name="پروندهٔ لغوشده")
    make_access(db_session, person, sup, dep, ceo)
    db_session.commit()

    period = _create_period(client, hr)
    created = client.post(
        "/api/evaluations", json={"subject_personnel_id": person.id}, headers=auth_header(sup)
    ).json()
    client.post(
        f"/api/evaluations/{created['id']}/cancel",
        json={"reason": "ثبت اشتباه بود و باید حذف شود"},
        headers=auth_header(hr),
    )

    body = client.get(f"/api/periods/{period['id']}/progress", headers=auth_header(hr)).json()

    assert body["started"] == 1
    assert body["finalized"] == 0
    assert body["in_progress"] == 0


def test_not_started_list_is_capped_but_the_total_is_not(client, db_session):
    """فهرست بریده می‌شود تا پاسخ چندهزارردیفی نشود، ولی عدد کل پنهان نمی‌ماند."""
    from app.api.routers.periods import NOT_STARTED_LIMIT

    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    for i in range(3):
        person = make_personnel(db_session, full_name=f"جامانده {i}")
        make_access(db_session, person, sup, dep, ceo)
    db_session.commit()

    period = _create_period(client, hr)
    body = client.get(f"/api/periods/{period['id']}/progress", headers=auth_header(hr)).json()

    assert body["not_started_total"] >= 3
    assert len(body["not_started"]) <= NOT_STARTED_LIMIT
    assert len(body["not_started"]) <= body["not_started_total"]
