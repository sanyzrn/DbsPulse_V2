"""P2-01 — تحلیل برای نقش‌هایی غیر از منابع انسانی.

خطرِ این قابلیت، خودِ قابلیت است: باز کردن آنالیتیکس به نقش‌هایی که عمداً به
رکوردهای خارج از زنجیرهٔ خودشان دسترسی ندارند، اگر بی‌احتیاط انجام شود دقیقاً
تبدیل می‌شود به راهی برای دور زدن همان کنترل دسترسی. پس نیمی از این فایل دربارهٔ
چیزی است که *نباید* برگردد.

سه چیز سنجیده می‌شود:

۱. هر نقش فقط نمای خودش را می‌بیند (و کارمند هیچ‌کدام را).
۲. آمارِ گروهیِ دیگران از سرکوب کوهورت رد می‌شود، ولی آمارِ خودِ ارزیاب نه —
   او همان نمره‌ها را خودش داده است.
۳. در نمای مدیریتی هیچ نام و شناسهٔ فردی نیست.
"""
import pytest

from app.models.enums import EvaluationStatus
from app.models.evaluation import EvaluationRecord
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


def _finalize_one(client, db_session, *, hr, sup, dep, ceo, personnel, scores=None):
    """یک پرونده را از آغاز تا نهایی‌شدن می‌برد و شناسه‌اش را برمی‌گرداند."""
    record_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": personnel.id},
        headers=auth_header(sup),
    ).json()["id"]
    payload = scores if scores is not None else full_valid_scores(active_indicators(db_session))
    client.put(
        f"/api/evaluations/{record_id}/scores",
        json={"scores": payload},
        headers=auth_header(sup),
    )
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(sup))
    client.post(f"/api/evaluations/{record_id}/hr-approve", headers=auth_header(hr))
    client.post(f"/api/evaluations/{record_id}/deputy-approve", headers=auth_header(dep))
    client.post(f"/api/evaluations/{record_id}/ceo-finalize", headers=auth_header(ceo))
    return record_id


@pytest.fixture()
def org(client, db_session):
    """دو مسئول واحد با سبک نمره‌دهی متفاوت — یکی سخت‌گیر، یکی آسان‌گیر.

    این تفاوت، خودِ چیزی است که نمای «آینهٔ ارزیاب» قرار است نشان بدهد؛ بدون آن،
    تست فقط می‌سنجد که endpoint دویست برمی‌گرداند.
    """
    hr = make_user(db_session, "hr")
    strict = make_user(db_session, "unit_supervisor")
    lenient = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    db_session.commit()

    indicators = active_indicators(db_session)
    strict_scores = [
        {**row, "score": 2, "evidence_text": "شواهد کافی برای نمرهٔ دو"}
        for row in full_valid_scores(indicators)
    ]
    lenient_scores = [{**row, "score": 4} for row in full_valid_scores(indicators)]

    for index in range(6):
        person = make_personnel(db_session, full_name=f"سخت‌گیر {index}", org_unit="واحد الف")
        make_access(db_session, person, strict, dep, ceo)
        db_session.commit()
        _finalize_one(
            client, db_session, hr=hr, sup=strict, dep=dep, ceo=ceo,
            personnel=person, scores=strict_scores,
        )
    for index in range(6):
        person = make_personnel(db_session, full_name=f"آسان‌گیر {index}", org_unit="واحد ب")
        make_access(db_session, person, lenient, dep, ceo)
        db_session.commit()
        _finalize_one(
            client, db_session, hr=hr, sup=lenient, dep=dep, ceo=ceo,
            personnel=person, scores=lenient_scores,
        )

    return {"hr": hr, "strict": strict, "lenient": lenient, "dep": dep, "ceo": ceo}


# ── دسترسی ──────────────────────────────────────────────────────────────────

def test_an_employee_gets_neither_view(client, db_session):
    personnel = make_personnel(db_session)
    employee = make_user(db_session, "employee", personnel_id=personnel.id)
    db_session.commit()

    assert client.get("/api/analytics/my-scoring", headers=auth_header(employee)).status_code == 403
    assert client.get("/api/analytics/executive", headers=auth_header(employee)).status_code == 403


def test_a_supervisor_cannot_open_the_executive_view(client, db_session):
    """نمای مدیریتی کلِ سازمان را تجمیع می‌کند؛ مسئول واحد فقط به حوزهٔ خودش
    دسترسی دارد و این نما آن مرز را دور می‌زند."""
    sup = make_user(db_session, "unit_supervisor")
    db_session.commit()

    assert client.get("/api/analytics/executive", headers=auth_header(sup)).status_code == 403


def test_the_ceo_has_no_scoring_mirror(client, db_session):
    """مدیرعامل نمره نمی‌دهد؛ «آینهٔ ارزیاب» برای او بی‌معناست."""
    ceo = make_user(db_session, "ceo")
    db_session.commit()

    assert client.get("/api/analytics/my-scoring", headers=auth_header(ceo)).status_code == 403


def test_both_views_need_authentication(client):
    assert client.get("/api/analytics/my-scoring").status_code == 401
    assert client.get("/api/analytics/executive").status_code == 401


# ── آینهٔ ارزیاب ────────────────────────────────────────────────────────────

def test_a_strict_rater_sees_the_gap_between_themselves_and_everyone_else(client, org):
    body = client.get("/api/analytics/my-scoring", headers=auth_header(org["strict"])).json()

    assert body["my_avg_score"] == 2.0
    # «بقیه» یعنی بدون خودم — وگرنه هرچه سهم من از نمره‌ها بیشتر باشد، فاصله‌ام
    # کوچک‌تر دیده می‌شود و ارزیابی که بیشترین انحراف را دارد کمترین را می‌بیند.
    assert body["org_avg_score"] == 4.0
    assert body["my_score_count"] > 0


def test_the_distribution_is_reported_as_shares_not_raw_counts(client, org):
    """ارزیابی با ۴۰ نمره را نمی‌شود با سازمانی که صدها نمره دارد از روی تعداد
    مقایسه کرد؛ عددی که خوانده می‌شود باید درصد باشد."""
    body = client.get("/api/analytics/my-scoring", headers=auth_header(org["strict"])).json()
    buckets = {b["score"]: b for b in body["distribution"]}

    assert buckets[2]["my_share_pct"] == 100.0
    assert buckets[4]["my_share_pct"] == 0.0
    # و بقیه دقیقاً برعکس
    assert buckets[4]["org_share_pct"] == 100.0
    assert buckets[2]["org_share_pct"] == 0.0


def test_the_biggest_deviation_comes_first(client, org):
    """ارزیاب باید اول جایی را ببیند که بیشتر از همه با بقیه فرق دارد، نه ترتیب فرم."""
    body = client.get("/api/analytics/my-scoring", headers=auth_header(org["strict"])).json()
    gaps = body["indicator_gaps"]

    assert len(gaps) > 1
    deviations = [
        abs(g["my_avg"] - g["org_avg"]) if g["org_avg"] is not None else -1 for g in gaps
    ]
    assert deviations == sorted(deviations, reverse=True)


def test_the_evidence_rate_reflects_voluntary_quality(client, org):
    """قاعدهٔ اجباری فقط نمرهٔ ۱ و ۵ را می‌گیرد؛ این عدد باید بگوید ارزیاب فراتر
    از اجبار چقدر شواهد می‌نویسد."""
    strict = client.get("/api/analytics/my-scoring", headers=auth_header(org["strict"])).json()
    lenient = client.get("/api/analytics/my-scoring", headers=auth_header(org["lenient"])).json()

    # سخت‌گیر برای همهٔ نمره‌های ۲ شواهد نوشته؛ آسان‌گیر برای نمره‌های ۴ ننوشته
    assert strict["evidence_rate_pct"] == 100.0
    assert lenient["evidence_rate_pct"] == 0.0


def test_a_rater_with_no_finalized_work_gets_empty_not_broken(client, db_session):
    """ارزیاب تازه‌وارد هم باید صفحه‌اش را ببیند — با اعداد خالی، نه با خطا."""
    sup = make_user(db_session, "unit_supervisor")
    db_session.commit()

    body = client.get("/api/analytics/my-scoring", headers=auth_header(sup)).json()

    assert body["my_score_count"] == 0
    assert body["my_avg_score"] is None
    assert body["evidence_rate_pct"] is None
    assert body["indicator_gaps"] == []


def test_the_organisation_average_is_suppressed_for_a_tiny_cohort(client, db_session):
    """اگر «بقیه» فقط چند نمره باشند، «میانگین سازمان» عملاً نمرهٔ همان چند نفر
    است — و به ارزیابی نشان داده می‌شود که به آن رکوردها دسترسی ندارد."""
    hr = make_user(db_session, "hr")
    mine = make_user(db_session, "unit_supervisor")
    other = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    db_session.commit()

    # فقط یک پروندهٔ نهایی‌شده برای «بقیه»
    person = make_personnel(db_session, full_name="تنها نمونهٔ دیگران")
    make_access(db_session, person, other, dep, ceo)
    db_session.commit()
    _finalize_one(client, db_session, hr=hr, sup=other, dep=dep, ceo=ceo, personnel=person)

    body = client.get("/api/analytics/my-scoring", headers=auth_header(mine)).json()

    assert body["org_people_count"] > 0, "داده هست"
    assert body["org_avg_score"] is None, "ولی جمعیتش برای نمایش بی‌نام کم است"


def test_my_own_numbers_are_never_suppressed(client, db_session):
    """استثنای عمدی: ارزیاب همان نمره‌ها را خودش داده و چیزی کشف نمی‌کند.
    سرکوب‌کردنش فقط او را از بازخوردِ خودش محروم می‌کند."""
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    person = make_personnel(db_session, full_name="تنها زیرمجموعه")
    make_access(db_session, person, sup, dep, ceo)
    db_session.commit()
    _finalize_one(client, db_session, hr=hr, sup=sup, dep=dep, ceo=ceo, personnel=person)

    body = client.get("/api/analytics/my-scoring", headers=auth_header(sup)).json()

    assert body["my_avg_score"] is not None
    assert body["my_score_count"] > 0


# ── نمای مدیریتی ────────────────────────────────────────────────────────────

def test_the_executive_view_carries_no_individual_identity(client, org):
    """مهم‌ترین تست این فایل.

    مدیرعامل عمداً به رکوردهای خارج از زنجیرهٔ خودش دسترسی ندارد. اگر نام یا
    شناسهٔ فردی از این نما بیرون بزند، تجمیع به یک دور زدنِ کنترل دسترسی تبدیل
    می‌شود. پاسخ به‌صورت متن خام بررسی می‌شود تا هیچ فیلد تازه‌ای — که فردا کسی
    «فقط برای کمک» اضافه می‌کند — از زیر این تست در نرود.
    """
    raw = client.get("/api/analytics/executive", headers=auth_header(org["ceo"])).text

    for forbidden in ("سخت‌گیر", "آسان‌گیر", "full_name", "personnel_id", "evaluation_code"):
        assert forbidden not in raw, f"نمای مدیریتی نباید «{forbidden}» را افشا کند"


def test_the_executive_view_answers_the_three_questions_it_exists_for(client, org):
    body = client.get("/api/analytics/executive", headers=auth_header(org["ceo"])).json()

    # کدام واحد عقب است؟
    units = {u["org_unit"]: u for u in body["by_org_unit"]}
    assert {"واحد الف", "واحد ب"} <= set(units)
    assert units["واحد ب"]["avg_final_pct"] > units["واحد الف"]["avg_final_pct"]

    # ترکیب توصیه‌ها به تمدید قرارداد چه می‌گوید؟
    assert body["recommendation_mix"]
    assert round(sum(slice_["share_pct"] for slice_ in body["recommendation_mix"])) == 100

    # چرخه چقدر طول می‌کشد؟
    assert body["cycle_time"]["finalized_count"] == 12
    assert body["cycle_time"]["median_days"] is not None


def test_a_thin_unit_is_counted_but_its_average_is_withheld(client, db_session):
    """تعداد پنهان نمی‌شود — دانستن «این واحد ۱ ارزیابی دارد» افشای عملکرد نیست،
    و صادقانه‌تر از حذف کامل ردیف است."""
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    person = make_personnel(db_session, full_name="تک‌نفرهٔ واحد", org_unit="واحد یک‌نفره")
    make_access(db_session, person, sup, dep, ceo)
    db_session.commit()
    _finalize_one(client, db_session, hr=hr, sup=sup, dep=dep, ceo=ceo, personnel=person)

    body = client.get("/api/analytics/executive", headers=auth_header(ceo)).json()
    thin = next(u for u in body["by_org_unit"] if u["org_unit"] == "واحد یک‌نفره")

    assert thin["count"] == 1
    assert thin["avg_final_pct"] is None


def test_contract_exposure_separates_expiring_from_unevaluated(client, db_session):
    """عدد مهم «چند نفر قراردادشان تمام می‌شود» نیست؛ «چند نفرشان بدون ارزیابی
    نهایی‌شده‌اند» است — یعنی تصمیم تمدید بدون داده گرفته می‌شود."""
    from datetime import date, timedelta

    ceo = make_user(db_session, "ceo")
    make_personnel(
        db_session,
        full_name="قرارداد رو به پایان",
        contract_end_date=date.today() + timedelta(days=20),
    )
    db_session.commit()

    body = client.get("/api/analytics/executive", headers=auth_header(ceo)).json()
    horizon_30 = next(h for h in body["contract_exposure"] if h["horizon_days"] == 30)

    assert horizon_30["expiring"] >= 1
    assert horizon_30["without_finalized_evaluation"] >= 1


def test_the_deputy_sees_both_views(client, db_session):
    """معاونت هم نمره می‌دهد (مسیر «مدیر») و هم تصمیم‌گیر است."""
    dep = make_user(db_session, "deputy")
    db_session.commit()

    assert client.get("/api/analytics/my-scoring", headers=auth_header(dep)).status_code == 200
    assert client.get("/api/analytics/executive", headers=auth_header(dep)).status_code == 200


def test_the_deputys_mirror_counts_the_manager_path(client, db_session):
    """در مسیر «مدیر» معاونت خودش نمره‌دهندهٔ اول است (unit_supervisor خالی).

    اگر این پرونده‌ها از آمار معاونت جا بیفتند، آینه‌اش نیمه‌خالی است و دقیقاً
    همان بخشی جا می‌ماند که خودش نمره داده."""
    hr = make_user(db_session, "hr")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    manager = make_personnel(
        db_session, full_name="پرسنل مدیر", job_title="مدیر", is_manager=True
    )
    make_access(db_session, manager, None, dep, ceo)
    db_session.commit()

    created = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": manager.id},
        headers=auth_header(dep),
    )
    assert created.status_code == 201, created.text
    record_id = created.json()["id"]

    client.put(
        f"/api/evaluations/{record_id}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(dep),
    )
    # مسیر کامل: معاونت ثبت می‌کند، منابع انسانی بررسی می‌کند، مدیرعامل نهایی.
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(dep))
    client.post(f"/api/evaluations/{record_id}/hr-approve", headers=auth_header(hr))
    client.post(f"/api/evaluations/{record_id}/ceo-finalize", headers=auth_header(ceo))

    record = db_session.get(EvaluationRecord, record_id)
    db_session.refresh(record)
    assert record.status == EvaluationStatus.finalized
    assert record.unit_supervisor_user_id is None, "مسیر مدیر: نمره‌دهندهٔ اول خود معاونت است"

    body = client.get("/api/analytics/my-scoring", headers=auth_header(dep)).json()
    assert body["my_score_count"] > 0
