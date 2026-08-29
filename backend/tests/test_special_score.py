"""امتیاز ویژه — نمرهٔ اختیاری بابت کاری خارج از شرح وظایف.

فرم به شاخص‌های ثابت نمره می‌دهد و همین درست است؛ ولی کاری که در هیچ شاخصی
نمی‌گنجد هم واقعی است. تا پیش از این، ارزیاب یا نادیده‌اش می‌گرفت یا نمرهٔ یک
شاخصِ بی‌ربط را بالا می‌برد تا جبرانش کند — یعنی نبودِ این قابلیت، دادهٔ
شاخص‌ها را هم آلوده می‌کرد.

چیزی که این فایل بیشتر از همه می‌سنجد این است که این «در» چقدر تنگ است: سقف
دارد، دلیل می‌خواهد، فقط در مرحلهٔ نمره‌دهی باز است، و هر بار در لاگ ممیزی
می‌نشیند. امتیاز ویژه‌ای که این چهار قید را نداشته باشد، فقط راهی برای دور زدن
فرم است.
"""
import pytest

from app.models.enums import Capability
from app.models.evaluation import EvaluationRecord
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


@pytest.fixture()
def org(db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    person = make_personnel(db_session, full_name="کارمند کارِ ویژه", org_unit="واحد الف")
    make_access(db_session, person, sup, dep, ceo)
    db_session.commit()
    return {"hr": hr, "sup": sup, "dep": dep, "ceo": ceo, "person": person}


def _open_draft(client, db_session, org, *, score=4):
    record_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": org["person"].id},
        headers=auth_header(org["sup"]),
    ).json()["id"]
    # نمرهٔ ۵ شواهد اجباری دارد (قاعدهٔ طرح فعال)، پس همیشه همراهش می‌آید؛
    # وگرنه ثبت پرونده به خطای شواهد می‌خورد نه به چیزی که این فایل می‌سنجد.
    scores = [
        {**row, "score": score, "evidence_text": "شواهد کافی برای این شاخص ثبت شده است"}
        for row in full_valid_scores(active_indicators(db_session))
    ]
    client.put(
        f"/api/evaluations/{record_id}/scores",
        json={"scores": scores},
        headers=auth_header(org["sup"]),
    )
    return record_id


def _set_bonus(client, actor, record_id, points, reason):
    return client.patch(
        f"/api/evaluations/{record_id}/special-score",
        json={"bonus_points": points, "bonus_reason": reason},
        headers=auth_header(actor),
    )


def test_the_bonus_is_added_to_the_final_score(client, db_session, org):
    record_id = _open_draft(client, db_session, org)
    before = client.post(
        f"/api/evaluations/{record_id}/submit", headers=auth_header(org["sup"])
    ).json()["final_weighted_pct"]

    # همان پرونده را برمی‌گردانیم تا با امتیاز ویژه دوباره ثبت شود؛ مقایسه
    # روی یک پروندهٔ واحد است، نه دو پروندهٔ متفاوت.
    client.post(
        f"/api/evaluations/{record_id}/return",
        json={"reason": "برای افزودن امتیاز ویژه"},
        headers=auth_header(org["hr"]),
    )
    assert _set_bonus(client, org["sup"], record_id, 3, "راه‌اندازی خط تولید جدید").status_code == 200
    after = client.post(
        f"/api/evaluations/{record_id}/submit", headers=auth_header(org["sup"])
    ).json()

    assert after["final_weighted_pct"] == pytest.approx(before + 3)
    # امتیازِ فرم دست‌نخورده می‌ماند — امتیاز ویژه جای نمرهٔ شاخص‌ها را نمی‌گیرد.
    assert after["base_weighted_pct"] == pytest.approx(before)
    assert after["bonus_points"] == 3
    assert after["general_score_pct"] == pytest.approx(80.0)


def test_a_bonus_without_a_reason_is_refused(client, db_session, org):
    record_id = _open_draft(client, db_session, org)
    response = _set_bonus(client, org["sup"], record_id, 2, "   ")
    assert response.status_code == 400
    assert "توضیح" in response.json()["detail"]


def test_a_bonus_reason_shorter_than_ten_characters_is_refused(client, db_session, org):
    record_id = _open_draft(client, db_session, org)
    response = _set_bonus(client, org["sup"], record_id, 2, "کار خوب")
    assert response.status_code == 400
    assert "۱۰" in response.json()["detail"]


def test_a_bonus_above_the_scheme_cap_is_refused_not_silently_trimmed(client, db_session, org):
    """بریدنِ بی‌صدا بدترین حالت است: ارزیاب ۹ می‌زند و ۵ ذخیره می‌شود."""
    record_id = _open_draft(client, db_session, org)
    response = _set_bonus(client, org["sup"], record_id, 9, "کار فوق‌العاده")
    assert response.status_code == 400
    assert "۵" in response.json()["detail"]

    record = db_session.get(EvaluationRecord, record_id)
    db_session.refresh(record)
    assert record.bonus_points is None


def test_the_bonus_cannot_push_the_final_score_past_one_hundred(client, db_session, org):
    """امتیاز نهایی در همه‌جای سامانه «درصد» است؛ ۱۰۳٪ هیچ معنایی ندارد.

    و مهم‌تر: عددی که بریده می‌شود از امتیازِ *اضافه‌شده* کم می‌شود، نه از جمع.
    وگرنه سند نهایی سه عددی نشان می‌داد که با هم جمع نمی‌شوند.
    """
    record_id = _open_draft(client, db_session, org, score=5)
    _set_bonus(client, org["sup"], record_id, 4, "پروژهٔ خارج از شرح وظایف")
    result = client.post(
        f"/api/evaluations/{record_id}/submit", headers=auth_header(org["sup"])
    ).json()

    assert result["base_weighted_pct"] == 100.0
    assert result["final_weighted_pct"] == 100.0
    assert result["bonus_points"] == 4  # ثبت‌شده می‌ماند، حتی وقتی جا برای اعمالش نیست


def test_zero_clears_the_reason_too(client, db_session, org):
    record_id = _open_draft(client, db_session, org)
    _set_bonus(client, org["sup"], record_id, 3, "دلیل اولیه")
    result = _set_bonus(client, org["sup"], record_id, 0, "دلیل اولیه").json()
    assert result["bonus_points"] == 0
    # دلیلِ باقی‌مانده از مقدار قبلی فقط گمراه‌کننده است.
    assert result["bonus_reason"] is None


def test_only_the_evaluator_of_this_case_can_award_it(client, db_session, org):
    record_id = _open_draft(client, db_session, org)
    other_sup = make_user(db_session, "unit_supervisor")
    db_session.commit()
    assert _set_bonus(client, other_sup, record_id, 2, "کار ویژه").status_code == 403
    assert _set_bonus(client, org["hr"], record_id, 2, "کار ویژه").status_code == 403
    assert _set_bonus(client, org["ceo"], record_id, 2, "کار ویژه").status_code == 403


def test_it_closes_once_the_case_leaves_the_scoring_stage(client, db_session, org):
    """پس از ثبت، امتیاز نهایی حساب شده و پرونده در زنجیرهٔ تأیید است.

    تغییر عددِ نتیجه در آن نقطه یعنی تأییدکننده روی چیزی امضا کرده که دیگر وجود
    ندارد. مسیرِ مخالفت، برگرداندن پرونده است — همان مسیر هر مخالفت دیگری.
    """
    record_id = _open_draft(client, db_session, org)
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(org["sup"]))
    assert _set_bonus(client, org["sup"], record_id, 2, "کار ویژه").status_code == 403


def test_the_manager_path_evaluator_can_award_it(client, db_session):
    """در مسیر «مدیر» نمره‌دهندهٔ اول معاونت است، پس همو باید بتواند ثبتش کند."""
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    manager = make_personnel(db_session, full_name="یک مدیر", org_unit="واحد ب", is_manager=True)
    make_access(db_session, manager, None, dep, ceo)
    db_session.commit()

    # مسیر «مدیر»: معاونت خودش پرونده را باز می‌کند و نمره‌دهنده‌اش هم خودش است.
    record_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": manager.id},
        headers=auth_header(dep),
    ).json()["id"]

    scores = [{**row, "score": 4} for row in full_valid_scores(active_indicators(db_session))]
    client.put(
        f"/api/evaluations/{record_id}/scores", json={"scores": scores}, headers=auth_header(dep)
    )
    assert _set_bonus(client, dep, record_id, 2, "بازطراحی فرایند انبار").status_code == 200

    result = client.post(
        f"/api/evaluations/{record_id}/submit", headers=auth_header(dep)
    ).json()
    assert result["bonus_points"] == 2
    assert result["final_weighted_pct"] == pytest.approx(result["base_weighted_pct"] + 2)


def test_it_lands_in_the_audit_log_with_the_previous_value(client, db_session, org):
    """یک تعدیل دستی روی نتیجهٔ یک تصمیم رسمی — دقیقاً چیزی که لاگ برایش هست."""
    record_id = _open_draft(client, db_session, org)
    _set_bonus(client, org["sup"], record_id, 3, "توضیح معتبر اول")
    _set_bonus(client, org["sup"], record_id, 1, "توضیح معتبر دوم")

    admin = make_user(db_session, "support", capabilities=list(Capability))
    db_session.commit()
    entries = client.get(
        f"/api/audit-log?evaluation_record_id={record_id}&event_type=special_score_set",
        headers=auth_header(admin),
    ).json()["items"]
    assert len(entries) == 2
    # هر دو ردیف در یک ثانیه ثبت می‌شوند، پس ترتیبِ برگشتی تضمینی نیست؛ ادعا
    # روی *زوجِ (قبلی، جدید)* است نه روی جای ردیف در فهرست.
    changes = {
        (
            (row["old_value"] or {}).get("bonus_points"),
            row["new_value"]["bonus_points"],
        )
        for row in entries
    }
    assert changes == {(None, 3), (3.0, 1)}


def test_the_employee_sees_what_the_bonus_was_for(client, db_session, org):
    """عدد بدون دلیلش، از دید کسی که نمره‌اش را گرفته، یک تعدیل بی‌توضیح است."""
    record_id = _open_draft(client, db_session, org)
    _set_bonus(client, org["sup"], record_id, 2, "مدیریت بحران قطعی برق")
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(org["sup"]))
    client.post(f"/api/evaluations/{record_id}/hr-approve", headers=auth_header(org["hr"]))
    client.post(f"/api/evaluations/{record_id}/deputy-approve", headers=auth_header(org["dep"]))
    client.post(f"/api/evaluations/{record_id}/ceo-finalize", headers=auth_header(org["ceo"]))

    employee = make_user(db_session, "employee", personnel_id=org["person"].id)
    db_session.commit()
    mine = client.get("/api/me/evaluations", headers=auth_header(employee)).json()["items"]
    assert mine[0]["bonus_points"] == 2
    assert mine[0]["bonus_reason"] == "مدیریت بحران قطعی برق"


def test_the_final_document_shows_the_bonus_and_its_reason(client, db_session, org):
    from app.services.snapshot import build_final_snapshot

    record_id = _open_draft(client, db_session, org)
    _set_bonus(client, org["sup"], record_id, 2.5, "استقرار سامانهٔ جدید انبار")
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(org["sup"]))
    client.post(f"/api/evaluations/{record_id}/hr-approve", headers=auth_header(org["hr"]))
    client.post(f"/api/evaluations/{record_id}/deputy-approve", headers=auth_header(org["dep"]))
    client.post(f"/api/evaluations/{record_id}/ceo-finalize", headers=auth_header(org["ceo"]))

    record = db_session.get(EvaluationRecord, record_id)
    db_session.refresh(record)
    snapshot = build_final_snapshot(db_session, record)
    assert snapshot["bonus_points"] == 2.5
    assert snapshot["bonus_reason"] == "استقرار سامانهٔ جدید انبار"
    # سه عددِ سند باید با هم بخوانند، وگرنه خواننده نمی‌داند کدام درست است.
    assert snapshot["base_weighted_pct"] + snapshot["bonus_points"] == pytest.approx(
        snapshot["final_weighted_pct"]
    )
