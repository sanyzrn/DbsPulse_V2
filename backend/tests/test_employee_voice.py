"""P0-06 — کارمند باید در فرایندی که دربارهٔ اوست، صدایی داشته باشد.

خروجی این سامانه توصیه دربارهٔ ادامهٔ اشتغال یک نفر است، ولی تا امروز آن یک نفر:
هیچ نمی‌دانست پرونده‌ای دربارهٔ او باز است، سندی را که دربارهٔ اوست نمی‌توانست
بگیرد (فقط HR می‌توانست)، و هیچ راهی برای ثبت مخالفت نداشت. «رؤیت» فقط ثبت می‌کرد
که او نتیجه را *دید*، نه این‌که پذیرفت.
"""

from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.models.enums import Capability, UserRole
from app.models.evaluation import EvaluationRecord
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


def _case(client, db_session, *, finalize: bool):
    hr = make_user(db_session, "hr", capabilities=[Capability.view_audit_log])
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session, full_name="کارمند صدادار")
    employee = make_user(db_session, "employee", personnel_id=personnel.id)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    evaluation = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    ).json()
    client.put(
        f"/api/evaluations/{evaluation['id']}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(sup),
    )
    client.post(f"/api/evaluations/{evaluation['id']}/submit", headers=auth_header(sup))
    if finalize:
        client.post(f"/api/evaluations/{evaluation['id']}/hr-approve", headers=auth_header(hr))
        client.post(f"/api/evaluations/{evaluation['id']}/deputy-approve", headers=auth_header(dep))
        client.post(f"/api/evaluations/{evaluation['id']}/ceo-finalize", headers=auth_header(ceo))

    return {
        "id": evaluation["id"],
        "code": evaluation["evaluation_code"],
        "hr": hr,
        "sup": sup,
        "dep": dep,
        "ceo": ceo,
        "employee": employee,
        "personnel": personnel,
    }


# ───────────────────────── نمای وضعیتِ پروندهٔ در جریان


def test_the_employee_can_see_that_a_case_about_them_is_open(client, db_session):
    case = _case(client, db_session, finalize=False)

    r = client.get("/api/me/evaluations/open", headers=auth_header(case["employee"]))

    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["evaluation_code"] == case["code"]
    assert rows[0]["stage_label"] == "در حال بررسی منابع انسانی"
    assert rows[0]["stage_entered_at"]


def test_the_status_view_leaks_no_scores(client, db_session):
    """نمرهٔ پیش‌نویس هنوز تصمیم نیست؛ دیدنش حق فرد نیست و اشتباه هم هست."""
    case = _case(client, db_session, finalize=False)

    row = client.get("/api/me/evaluations/open", headers=auth_header(case["employee"])).json()[0]

    for leaked in ("final_weighted_pct", "general_score_pct", "scores", "comments", "recommendation"):
        assert leaked not in row, f"نمای وضعیت نباید {leaked} را نشان دهد"


def test_the_status_view_shows_only_my_own_case(client, db_session):
    mine = _case(client, db_session, finalize=False)
    other = _case(client, db_session, finalize=False)

    rows = client.get("/api/me/evaluations/open", headers=auth_header(mine["employee"])).json()

    assert [r["evaluation_code"] for r in rows] == [mine["code"]]
    assert other["code"] not in [r["evaluation_code"] for r in rows]


def test_a_finalized_case_leaves_the_open_list(client, db_session):
    case = _case(client, db_session, finalize=True)

    assert client.get("/api/me/evaluations/open", headers=auth_header(case["employee"])).json() == []


# ───────────────────────── سند خودِ فرد


def test_the_subject_can_download_their_own_document(client, db_session):
    """سندی که دربارهٔ یک نفر است باید در اختیار خودش باشد."""
    case = _case(client, db_session, finalize=True)

    r = client.get(f"/api/evaluations/{case['id']}/summary.pdf", headers=auth_header(case["employee"]))

    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"


def test_downloading_your_own_document_is_audited(client, db_session):
    case = _case(client, db_session, finalize=True)
    client.get(f"/api/evaluations/{case['id']}/summary.pdf", headers=auth_header(case["employee"]))

    events = client.get(
        "/api/audit-log", params={"event_type": "pdf_downloaded"}, headers=auth_header(case["hr"])
    ).json()
    rows = events["items"] if isinstance(events, dict) and "items" in events else events
    entry = next(r for r in rows if r["evaluation_record_id"] == case["id"])
    assert entry["new_value"]["by_subject"] is True


def test_an_employee_cannot_download_someone_elses_document(client, db_session):
    mine = _case(client, db_session, finalize=True)
    other = _case(client, db_session, finalize=True)

    r = client.get(f"/api/evaluations/{other['id']}/summary.pdf", headers=auth_header(mine["employee"]))

    assert r.status_code == 403


def test_chain_roles_still_cannot_download_the_document(client, db_session):
    """گشودن سند برای سوژه نباید سهواً برای بقیهٔ زنجیره هم بازش کند."""
    case = _case(client, db_session, finalize=True)

    for actor in ("sup", "dep", "ceo"):
        r = client.get(f"/api/evaluations/{case['id']}/summary.pdf", headers=auth_header(case[actor]))
        assert r.status_code == 403, actor


# ───────────────────────── اعتراض


def test_the_employee_can_object_after_acknowledging(client, db_session):
    case = _case(client, db_session, finalize=True)
    client.post(f"/api/me/evaluations/{case['id']}/acknowledge", headers=auth_header(case["employee"]))

    r = client.post(
        f"/api/me/evaluations/{case['id']}/object",
        json={"reason": "شواهد ارائه‌شده برای شاخص تعهد سازمانی با گزارش حضور و غیاب نمی‌خواند"},
        headers=auth_header(case["employee"]),
    )

    assert r.status_code == 200
    assert r.json()["objection_at"] is not None
    assert "حضور و غیاب" in r.json()["objection_reason"]


def test_objecting_requires_acknowledging_first(client, db_session):
    case = _case(client, db_session, finalize=True)

    r = client.post(
        f"/api/me/evaluations/{case['id']}/object",
        json={"reason": "اعتراض زودهنگام"},
        headers=auth_header(case["employee"]),
    )

    assert r.status_code == 400
    # پیام باید بگوید *چه کاری* اول لازم است، نه فقط «نمی‌شود». به واژهٔ خاصی
    # گره نمی‌خورد: متن‌های رو به کارمند عمداً از «رؤیت» به «مشاهده» تغییر
    # کردند و تستی که یک کلمه را قفل کند، جلوی بهتر شدن زبان را می‌گیرد.
    detail = r.json()["detail"]
    assert "مشاهده" in detail and "اعتراض" in detail, detail

    # و اعتراضی ثبت نشده باشد — ادعای اصلی همین است، نه متن پیام.
    mine = client.get("/api/me/evaluations", headers=auth_header(case["employee"])).json()
    assert all(item["objection_at"] is None for item in mine["items"])


def test_the_objection_window_closes(client, db_session):
    """پرونده بالاخره باید قطعی شود؛ پنجرهٔ باز تا ابد یعنی هیچ نتیجه‌ای نهایی نیست."""
    case = _case(client, db_session, finalize=True)
    client.post(f"/api/me/evaluations/{case['id']}/acknowledge", headers=auth_header(case["employee"]))

    record = db_session.get(EvaluationRecord, case["id"])
    record.acknowledged_at = datetime.now(UTC) - timedelta(days=settings.objection_window_days + 1)
    db_session.commit()

    r = client.post(
        f"/api/me/evaluations/{case['id']}/object",
        json={"reason": "خیلی دیر"},
        headers=auth_header(case["employee"]),
    )

    assert r.status_code == 400
    assert "مهلت" in r.json()["detail"]


def test_only_one_objection_per_record(client, db_session):
    case = _case(client, db_session, finalize=True)
    client.post(f"/api/me/evaluations/{case['id']}/acknowledge", headers=auth_header(case["employee"]))
    client.post(
        f"/api/me/evaluations/{case['id']}/object",
        json={"reason": "اعتراض اول"},
        headers=auth_header(case["employee"]),
    )

    again = client.post(
        f"/api/me/evaluations/{case['id']}/object",
        json={"reason": "اعتراض دوم"},
        headers=auth_header(case["employee"]),
    )

    assert again.status_code == 400


def test_an_objection_notifies_hr_and_is_audited(client, db_session):
    case = _case(client, db_session, finalize=True)
    client.post(f"/api/me/evaluations/{case['id']}/acknowledge", headers=auth_header(case["employee"]))
    client.post(
        f"/api/me/evaluations/{case['id']}/object",
        json={"reason": "امتیاز شاخص کیفیت با بازخوردهای دریافتی هم‌خوان نیست"},
        headers=auth_header(case["employee"]),
    )

    notes = client.get("/api/notifications", headers=auth_header(case["hr"])).json()
    rows = notes["items"] if isinstance(notes, dict) else notes
    assert any("اعتراض" in n["message"] for n in rows)

    events = client.get(
        "/api/audit-log",
        params={"event_type": "evaluation_objection_filed"},
        headers=auth_header(case["hr"]),
    ).json()
    entries = events["items"] if isinstance(events, dict) and "items" in events else events
    assert any(e["evaluation_record_id"] == case["id"] for e in entries)


def test_the_objection_does_not_alter_the_result_or_the_document(client, db_session):
    """سند نهایی هش و QR تأیید دارد؛ اعتراض یک رکورد موازی است، نه بازنویسی آن."""
    case = _case(client, db_session, finalize=True)
    before = client.get(f"/api/evaluations/{case['id']}", headers=auth_header(case["hr"])).json()
    pdf_before = client.get(f"/api/evaluations/{case['id']}/summary.pdf", headers=auth_header(case["hr"])).content

    client.post(f"/api/me/evaluations/{case['id']}/acknowledge", headers=auth_header(case["employee"]))
    client.post(
        f"/api/me/evaluations/{case['id']}/object",
        json={"reason": "اعتراض"},
        headers=auth_header(case["employee"]),
    )

    after = client.get(f"/api/evaluations/{case['id']}", headers=auth_header(case["hr"])).json()
    pdf_after = client.get(f"/api/evaluations/{case['id']}/summary.pdf", headers=auth_header(case["hr"])).content

    assert after["final_weighted_pct"] == before["final_weighted_pct"]
    assert after["status"] == "finalized"
    assert pdf_after == pdf_before, "سند بایت‌به‌بایت باید پایدار بماند"


def test_hr_resolves_the_objection_and_the_employee_is_told(client, db_session):
    case = _case(client, db_session, finalize=True)
    client.post(f"/api/me/evaluations/{case['id']}/acknowledge", headers=auth_header(case["employee"]))
    client.post(
        f"/api/me/evaluations/{case['id']}/object",
        json={"reason": "امتیاز منصفانه نیست"},
        headers=auth_header(case["employee"]),
    )

    r = client.post(
        f"/api/evaluations/{case['id']}/resolve-objection",
        json={"resolution": "با مسئول واحد بررسی شد؛ شواهد تکمیلی به پرونده افزوده شد"},
        headers=auth_header(case["hr"]),
    )

    assert r.status_code == 200
    assert r.json()["objection_resolved_at"] is not None

    mine = client.get("/api/me/evaluations", headers=auth_header(case["employee"])).json()
    record = mine["items"][0]
    assert "شواهد تکمیلی" in record["objection_resolution"]

    notes = client.get("/api/notifications", headers=auth_header(case["employee"])).json()
    rows = notes["items"] if isinstance(notes, dict) else notes
    assert any("پاسخ داده شد" in n["message"] for n in rows)


def test_resolving_requires_an_objection_and_happens_once(client, db_session):
    case = _case(client, db_session, finalize=True)

    none_filed = client.post(
        f"/api/evaluations/{case['id']}/resolve-objection",
        json={"resolution": "پاسخ به چیزی که نیست"},
        headers=auth_header(case["hr"]),
    )
    assert none_filed.status_code == 400

    client.post(f"/api/me/evaluations/{case['id']}/acknowledge", headers=auth_header(case["employee"]))
    client.post(
        f"/api/me/evaluations/{case['id']}/object",
        json={"reason": "اعتراض"},
        headers=auth_header(case["employee"]),
    )
    client.post(
        f"/api/evaluations/{case['id']}/resolve-objection",
        json={"resolution": "پاسخ اول"},
        headers=auth_header(case["hr"]),
    )
    twice = client.post(
        f"/api/evaluations/{case['id']}/resolve-objection",
        json={"resolution": "پاسخ دوم"},
        headers=auth_header(case["hr"]),
    )
    assert twice.status_code == 400


def test_an_employee_cannot_object_to_someone_elses_record(client, db_session):
    mine = _case(client, db_session, finalize=True)
    other = _case(client, db_session, finalize=True)
    client.post(f"/api/me/evaluations/{other['id']}/acknowledge", headers=auth_header(other["employee"]))

    r = client.post(
        f"/api/me/evaluations/{other['id']}/object",
        json={"reason": "پروندهٔ دیگری"},
        headers=auth_header(mine["employee"]),
    )

    # ۴۰۴ نه ۴۰۳: وجودِ پروندهٔ دیگران هم نباید لو برود
    assert r.status_code == 404


def test_non_hr_roles_cannot_resolve_an_objection(client, db_session):
    case = _case(client, db_session, finalize=True)
    client.post(f"/api/me/evaluations/{case['id']}/acknowledge", headers=auth_header(case["employee"]))
    client.post(
        f"/api/me/evaluations/{case['id']}/object",
        json={"reason": "اعتراض"},
        headers=auth_header(case["employee"]),
    )

    for actor in ("sup", "dep", "ceo"):
        r = client.post(
            f"/api/evaluations/{case['id']}/resolve-objection",
            json={"resolution": "تلاش"},
            headers=auth_header(case[actor]),
        )
        assert r.status_code == 403, actor


# ───────────────────────── خودارزیابی


def _indicator_payload(db_session, score: int):
    return {
        "scores": [{"indicator_id": i.id, "score": score, "note": "توضیح خودم"} for i in active_indicators(db_session)],
        "note": "دستاورد اصلی من در این دوره راه‌اندازی سامانهٔ گزارش‌گیری بود",
    }


def test_the_employee_can_submit_a_self_assessment_while_the_case_is_open(client, db_session):
    case = _case(client, db_session, finalize=False)
    # پرونده در وضعیت submitted است؛ برش می‌گردانیم به draft تا پنجرهٔ خودارزیابی باز باشد
    client.post(
        f"/api/evaluations/{case['id']}/return",
        json={"reason": "بازگشت برای تکمیل"},
        headers=auth_header(case["hr"]),
    )

    r = client.post(
        f"/api/me/evaluations/{case['id']}/self-assessment",
        json=_indicator_payload(db_session, 5),
        headers=auth_header(case["employee"]),
    )

    assert r.status_code == 200
    assert r.json()["submitted_at"] is not None
    assert len(r.json()["scores"]) == 20
    assert "گزارش‌گیری" in r.json()["note"]
    current = client.get("/api/me/self-assessment/current", headers=auth_header(case["employee"])).json()
    assert current["state"] == "submitted"


def test_every_role_except_deputy_and_ceo_can_self_assess_its_own_record(client, db_session):
    """قاعده زنجیره‌محور است نه نقش‌محور: هر کسی که *موضوعِ* پرونده است.

    `_case` پرونده را در `submitted` می‌گذارد و پنجرهٔ خودارزیابی آن‌جا بسته است،
    پس اول باید به مرحلهٔ ثبت برگردد — وگرنه این تست به‌جای نقش، پنجره را می‌سنجد
    و برای همهٔ نقش‌ها یکسان رد می‌شود.
    """
    for role in (UserRole.hr, UserRole.unit_supervisor, UserRole.support):
        case = _case(client, db_session, finalize=False)
        case["employee"].role = role
        db_session.commit()
        client.post(
            f"/api/evaluations/{case['id']}/return",
            json={"reason": "بازگشت"},
            headers=auth_header(case["hr"]),
        )

        response = client.post(
            f"/api/me/evaluations/{case['id']}/self-assessment",
            json=_indicator_payload(db_session, 4),
            headers=auth_header(case["employee"]),
        )
        assert response.status_code == 200, role


def test_deputy_and_ceo_have_no_self_assessment_access(client, db_session):
    case = _case(client, db_session, finalize=False)
    for actor in ("dep", "ceo"):
        response = client.get("/api/me/evaluations/open", headers=auth_header(case[actor]))
        assert response.status_code == 403, actor


def test_hr_cannot_invite_a_deputy_or_ceo_to_self_assess(client, db_session):
    for role in (UserRole.deputy, UserRole.ceo):
        case = _case(client, db_session, finalize=False)
        case["employee"].role = role
        db_session.commit()

        response = client.post(
            f"/api/personnel/{case['personnel'].id}/invite-self-assessment",
            headers=auth_header(case["hr"]),
        )
        assert response.status_code == 400, role
        assert "مشمول خودارزیابی نیستند" in response.json()["detail"]


def test_the_self_assessment_never_enters_the_result(client, db_session):
    """قلب این بخش: نظر فرد یک دیدگاه دوم است، نه یک رأی.

    کارمند به همهٔ شاخص‌ها ۵ می‌دهد در حالی که ارزیاب ۳ داده؛ نتیجهٔ نهایی باید
    دقیقاً همان چیزی بماند که از امتیاز ارزیاب درمی‌آید.
    """
    case = _case(client, db_session, finalize=False)
    client.post(
        f"/api/evaluations/{case['id']}/return",
        json={"reason": "بازگشت"},
        headers=auth_header(case["hr"]),
    )
    client.post(
        f"/api/me/evaluations/{case['id']}/self-assessment",
        json=_indicator_payload(db_session, 5),
        headers=auth_header(case["employee"]),
    )

    client.post(f"/api/evaluations/{case['id']}/submit", headers=auth_header(case["sup"]))
    client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(case["hr"]))
    client.post(f"/api/evaluations/{case['id']}/deputy-approve", headers=auth_header(case["dep"]))
    final = client.post(f"/api/evaluations/{case['id']}/ceo-finalize", headers=auth_header(case["ceo"])).json()

    # امتیاز ارزیاب همه ۳ بود (full_valid_scores) → دقیقاً ۶۰٪
    assert final["final_weighted_pct"] == 60.0, "خودارزیابی نباید در میانگین اثر بگذارد"


def test_only_hr_ever_sees_a_self_assessment(client, db_session):
    """قاعده، نه تنظیم: مسئول مستقیم هیچ‌وقت نمی‌بیند — نه پیش از ثبتِ نمره‌اش، نه بعدش.

    و منابع انسانی از همان لحظهٔ ثبت می‌بیند. شرطِ «فقط پس از ثبتِ نمرهٔ مدیر»
    منابع انسانی را کور می‌کرد: دعوت می‌فرستاد و هیچ راهی نداشت بفهمد جواب گرفته
    یا نه. کاملِ *شدنِ جدولِ مقایسه* چیزِ دیگری است و خودِ جدول نشانش می‌دهد.
    """
    case = _case(client, db_session, finalize=False)
    client.post(
        f"/api/evaluations/{case['id']}/return",
        json={"reason": "بازگشت"},
        headers=auth_header(case["hr"]),
    )
    client.post(
        f"/api/me/evaluations/{case['id']}/self-assessment",
        json=_indicator_payload(db_session, 5),
        headers=auth_header(case["employee"]),
    )

    def detail(actor):
        return client.get(f"/api/evaluations/{case['id']}", headers=auth_header(case[actor])).json()

    # پیش از ثبتِ نمرهٔ ارزیاب
    hr_view = detail("hr")
    assert hr_view["self_assessment"] is not None
    assert len(hr_view["self_assessment"]["scores"]) == 20
    for actor in ("sup", "dep", "ceo"):
        assert detail(actor)["self_assessment"] is None, actor

    # و پس از آن هم — این همان چیزی است که گاردِ زمانیِ قدیمی باز می‌کرد.
    # نمره‌ها از پیش ثبت شده‌اند و `return` پاکشان نمی‌کند، پس فقط ثبتِ دوباره.
    client.post(f"/api/evaluations/{case['id']}/submit", headers=auth_header(case["sup"]))
    assert detail("hr")["scores"][0]["score"] == 3
    for actor in ("sup", "dep", "ceo"):
        assert detail(actor)["self_assessment"] is None, actor


def test_a_case_without_a_self_assessment_is_perfectly_normal(client, db_session):
    """اختیاری یعنی اختیاری: نبودش نباید چیزی را بشکند."""
    case = _case(client, db_session, finalize=True)

    detail = client.get(f"/api/evaluations/{case['id']}", headers=auth_header(case["hr"])).json()

    assert detail["self_assessment"] is None
    assert detail["final_weighted_pct"] == 60.0


def test_the_self_assessment_is_locked_after_submission(client, db_session):
    """اگر بعد از دیدن نمرهٔ ارزیاب قابل ویرایش بود، دیگر دیدگاه مستقلی نبود."""
    case = _case(client, db_session, finalize=False)
    client.post(
        f"/api/evaluations/{case['id']}/return",
        json={"reason": "بازگشت"},
        headers=auth_header(case["hr"]),
    )
    client.post(
        f"/api/me/evaluations/{case['id']}/self-assessment",
        json=_indicator_payload(db_session, 5),
        headers=auth_header(case["employee"]),
    )

    again = client.post(
        f"/api/me/evaluations/{case['id']}/self-assessment",
        json=_indicator_payload(db_session, 1),
        headers=auth_header(case["employee"]),
    )

    assert again.status_code == 400
    assert "قابل تغییر نیست" in again.json()["detail"]


def test_the_contract_form_stays_open_after_the_evaluator_has_scored(client, db_session):
    """ثبت نمرهٔ ارزیاب، خودارزیابی مستقلِ قرارداد را باز یا بسته نمی‌کند."""
    case = _case(client, db_session, finalize=False)  # وضعیت: submitted

    r = client.post(
        f"/api/me/evaluations/{case['id']}/self-assessment",
        json=_indicator_payload(db_session, 5),
        headers=auth_header(case["employee"]),
    )

    assert r.status_code == 200


def _self_assessment_notes(client, user):
    notes = client.get("/api/notifications", headers=auth_header(user)).json()
    rows = notes["items"] if isinstance(notes, dict) else notes
    return [n for n in rows if "خودارزیابی" in n["message"]]


def test_submission_notifies_hr_and_never_the_scorer(client, db_session):
    case = _case(client, db_session, finalize=False)
    client.post(
        f"/api/evaluations/{case['id']}/return",
        json={"reason": "بازگشت"},
        headers=auth_header(case["hr"]),
    )
    client.post(
        f"/api/me/evaluations/{case['id']}/self-assessment",
        json=_indicator_payload(db_session, 4),
        headers=auth_header(case["employee"]),
    )

    assert _self_assessment_notes(client, case["sup"]) == []
    rows = _self_assessment_notes(client, case["hr"])
    assert rows, "منابع انسانی باید خبردار شود"
    assert "قرارداد جاری" in rows[0]["message"]


def test_an_employee_cannot_self_assess_someone_elses_record(client, db_session):
    mine = _case(client, db_session, finalize=False)
    other = _case(client, db_session, finalize=False)

    r = client.post(
        f"/api/me/evaluations/{other['id']}/self-assessment",
        json=_indicator_payload(db_session, 5),
        headers=auth_header(mine["employee"]),
    )

    assert r.status_code == 404


# ───────────────────────── پنجرهٔ خودارزیابی: پیوسته و یک‌جا تعریف‌شده


def test_hr_approval_does_not_close_the_contract_form(client, db_session):
    case = _case(client, db_session, finalize=False)  # وضعیت: submitted
    client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(case["hr"]))

    r = client.post(
        f"/api/me/evaluations/{case['id']}/self-assessment",
        json=_indicator_payload(db_session, 5),
        headers=auth_header(case["employee"]),
    )

    assert r.status_code == 200


def test_the_open_case_no_longer_owns_the_self_assessment_window(client, db_session):
    case = _case(client, db_session, finalize=False)  # وضعیت: submitted

    closed = client.get("/api/me/evaluations/open", headers=auth_header(case["employee"])).json()
    assert closed[0]["self_assessment_open"] is False

    client.post(
        f"/api/evaluations/{case['id']}/return",
        json={"reason": "بازگشت"},
        headers=auth_header(case["hr"]),
    )
    opened = client.get("/api/me/evaluations/open", headers=auth_header(case["employee"])).json()
    assert opened[0]["self_assessment_open"] is False
    current = client.get("/api/me/self-assessment/current", headers=auth_header(case["employee"])).json()
    assert current["open"] is True


# ───────────────────────── دعوت: یادآوری، نه بن‌بست


def test_opening_an_evaluation_does_not_notify_the_employee(client, db_session):
    case = _case(client, db_session, finalize=False)
    notes = client.get("/api/notifications", headers=auth_header(case["employee"])).json()
    rows = notes["items"] if isinstance(notes, dict) else notes
    invites = [n for n in rows if n["type"] == "self_assessment_invited"]

    assert invites == []


def test_the_invitation_can_be_sent_again_as_a_reminder(client, db_session):
    """دعوتِ دوم خطا نیست.

    پیش از این بارِ دوم ۴۰۹ می‌گرفت، برای همیشه — یعنی اگر اعلان گم می‌شد،
    منابع انسانی هیچ راهی برای رساندنِ دوبارهٔ خبر نداشت.
    """
    case = _case(client, db_session, finalize=False)
    client.post(
        f"/api/evaluations/{case['id']}/return",
        json={"reason": "بازگشت"},
        headers=auth_header(case["hr"]),
    )
    url = f"/api/personnel/{case['personnel'].id}/invite-self-assessment"

    first = client.post(url, headers=auth_header(case["hr"]))
    second = client.post(url, headers=auth_header(case["hr"]))

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    notes = client.get("/api/notifications", headers=auth_header(case["employee"])).json()
    rows = notes["items"] if isinstance(notes, dict) else notes
    invites = [n for n in rows if n["type"] == "self_assessment_invited"]
    assert len(invites) == 2, "هر درخواست HR باید یک یادآوری ساده بسازد"
    assert sum("یادآوری" in n["message"] for n in invites) == 2


def test_a_reminder_is_refused_once_the_person_has_answered(client, db_session):
    case = _case(client, db_session, finalize=False)
    client.post(
        f"/api/evaluations/{case['id']}/return",
        json={"reason": "بازگشت"},
        headers=auth_header(case["hr"]),
    )
    client.post(
        f"/api/me/evaluations/{case['id']}/self-assessment",
        json=_indicator_payload(db_session, 3),
        headers=auth_header(case["employee"]),
    )

    again = client.post(
        f"/api/personnel/{case['personnel'].id}/invite-self-assessment",
        headers=auth_header(case["hr"]),
    )

    assert again.status_code == 400
    assert "قبلاً ثبت کرده" in again.json()["detail"]
