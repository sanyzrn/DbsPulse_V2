"""P1-04 — طرح نمره‌دهیِ نسخه‌دار.

قابلیت این‌جا دو نیمه دارد و نیمهٔ دوم مهم‌تر است:

۱. HR می‌تواند وزن‌ها، قاعدهٔ شواهد و جدول آستانه‌ها را عوض کند بدون تغییر کد.
۲. **این کار معنای پرونده‌های گذشته را عوض نمی‌کند.**

بدون نیمهٔ دوم، این قابلیت از نبودش بدتر بود: پرونده‌ای که پارسال «تمدید با
شرایط استاندارد» گرفته، امروز بی‌صدا «عدم تمدید» نشان می‌داد — بدون این‌که هیچ
نمره‌ای عوض شده باشد. در سامانه‌ای که خروجی‌اش تصمیم تمدید قرارداد است، این
خرابیِ ساکت است.

پس بیشتر این فایل دربارهٔ چیزی است که *نباید* عوض شود.
"""
import pytest

from app.models.enums import SchemeStatus
from app.models.evaluation import EvaluationRecord
from app.models.scoring_scheme import ScoringScheme
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)

# طرحی که آستانه‌ها را جابه‌جا می‌کند: هرچه زیر ۹۵ باشد پایین‌ترین برچسب را
# می‌گیرد. روی هر دادهٔ واقعی اثر می‌گذارد، پس تست‌ها چیزی برای دیدن دارند.
STRICTER = {
    "name": "طرح سخت‌گیرانه",
    "general_section_weight": 0.5,
    "specialized_section_weight": 0.5,
    "evidence_required_scores": [1, 2, 5],
    "evidence_min_words": 5,
    "evidence_max_words": 30,
    "thresholds": [
        {"upper_exclusive": 95, "label": "نیازمند بازنگری"},
        {"upper_exclusive": 101, "label": "قابل تمدید"},
    ],
    "indicator_weights": {},
}


def _finalize(client, db_session, *, hr, sup, dep, ceo, personnel, score=4):
    indicators = active_indicators(db_session)
    scores = [{**row, "score": score} for row in full_valid_scores(indicators)]
    record_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": personnel.id},
        headers=auth_header(sup),
    ).json()["id"]
    client.put(
        f"/api/evaluations/{record_id}/scores", json={"scores": scores}, headers=auth_header(sup)
    )
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(sup))
    client.post(f"/api/evaluations/{record_id}/hr-approve", headers=auth_header(hr))
    client.post(f"/api/evaluations/{record_id}/deputy-approve", headers=auth_header(dep))
    client.post(f"/api/evaluations/{record_id}/ceo-finalize", headers=auth_header(ceo))
    return record_id


@pytest.fixture()
def org(db_session):
    """دو کاربر HR — فعال‌سازی دو نفره بدون نفر دوم قابل آزمودن نیست."""
    hr = make_user(db_session, "hr")
    hr2 = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    person = make_personnel(db_session, full_name="موضوع طرح", org_unit="واحد طرح")
    make_access(db_session, person, sup, dep, ceo)
    db_session.commit()
    return {"hr": hr, "hr2": hr2, "sup": sup, "dep": dep, "ceo": ceo, "person": person}


def _draft(client, actor, **overrides):
    return client.post(
        "/api/scoring-schemes", json={**STRICTER, **overrides}, headers=auth_header(actor)
    )


# ── نسخهٔ پایه ──────────────────────────────────────────────────────────────

def test_version_one_exists_and_matches_the_old_constants(client, db_session, org):
    """مایگریشن باید نسخهٔ ۱ را دقیقاً از قواعد قبلی ساخته باشد، وگرنه همین
    استقرار رفتار سامانه را عوض کرده است."""
    from app.core import constants

    body = client.get("/api/scoring-schemes", headers=auth_header(org["hr"])).json()
    base = next(s for s in body if s["version"] == 1)

    assert base["status"] == "active"
    assert base["general_section_weight"] == constants.GENERAL_SECTION_WEIGHT
    assert base["specialized_section_weight"] == constants.SPECIALIZED_SECTION_WEIGHT
    assert base["evidence_min_words"] == constants.EVIDENCE_REQUIRED_MIN_WORDS
    assert base["evidence_required_scores"] == list(constants.EVIDENCE_REQUIRED_SCORES)
    assert [b["label"] for b in base["thresholds"]] == [
        label for _, label in constants.FINAL_RESULT_THRESHOLDS
    ]


def test_a_new_record_is_stamped_with_the_active_scheme(client, db_session, org):
    record_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": org["person"].id},
        headers=auth_header(org["sup"]),
    ).json()["id"]

    record = db_session.get(EvaluationRecord, record_id)
    db_session.refresh(record)
    assert record.scoring_scheme_id is not None
    scheme = db_session.get(ScoringScheme, record.scoring_scheme_id)
    assert scheme.status is SchemeStatus.active


# ── پایداری تاریخ: قلب این قابلیت ───────────────────────────────────────────

def test_activating_a_new_scheme_does_not_rewrite_finalised_records(client, db_session, org):
    """مهم‌ترین تست این فایل.

    پرونده نهایی می‌شود، بعد HR طرحی فعال می‌کند که آستانه‌هایش کاملاً متفاوت
    است. نتیجهٔ ثبت‌شدهٔ آن پرونده نباید تکان بخورد.
    """
    record_id = _finalize(client, db_session, **{k: org[k] for k in ("hr", "sup", "dep", "ceo")},
                          personnel=org["person"])
    record = db_session.get(EvaluationRecord, record_id)
    db_session.refresh(record)
    before = (
        float(record.final_weighted_pct),
        record.recommendation,
        record.scoring_scheme_id,
    )

    scheme_id = _draft(client, org["hr"]).json()["id"]
    activated = client.post(
        f"/api/scoring-schemes/{scheme_id}/activate", headers=auth_header(org["hr2"])
    )
    assert activated.status_code == 200

    db_session.expire_all()
    record = db_session.get(EvaluationRecord, record_id)
    after = (
        float(record.final_weighted_pct),
        record.recommendation,
        record.scoring_scheme_id,
    )
    assert after == before, "فعال‌سازی طرح تازه نباید پروندهٔ نهایی‌شده را عوض کند"


def test_an_open_case_keeps_the_rules_it_was_opened_under(client, db_session, org):
    """پرونده‌ای که وسط چرخه است هم با قواعد *خودش* بسته می‌شود.

    وگرنه ارزیابی که فرم را نیمه‌کاره رها کرده بود، پرونده‌اش با قواعدی نهایی
    می‌شد که هرگز ندیده — از جمله قاعدهٔ شواهدی که موقع پرکردن فرم وجود نداشت.
    """
    record_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": org["person"].id},
        headers=auth_header(org["sup"]),
    ).json()["id"]
    indicators = active_indicators(db_session)
    # نمرهٔ ۲ زیر طرح پایه شواهد لازم ندارد، ولی زیر طرح سخت‌گیرانه دارد
    scores = [{**row, "score": 2} for row in full_valid_scores(indicators)]
    client.put(
        f"/api/evaluations/{record_id}/scores",
        json={"scores": scores},
        headers=auth_header(org["sup"]),
    )

    scheme_id = _draft(client, org["hr"]).json()["id"]
    client.post(f"/api/scoring-schemes/{scheme_id}/activate", headers=auth_header(org["hr2"]))

    # ثبت باید همچنان قبول شود: قاعدهٔ شواهدِ *این پرونده* همان قاعدهٔ قدیمی است
    submitted = client.post(
        f"/api/evaluations/{record_id}/submit", headers=auth_header(org["sup"])
    )
    assert submitted.status_code == 200, submitted.text


def test_a_record_created_after_activation_uses_the_new_rules(client, db_session, org):
    scheme_id = _draft(client, org["hr"]).json()["id"]
    client.post(f"/api/scoring-schemes/{scheme_id}/activate", headers=auth_header(org["hr2"]))

    other = make_personnel(db_session, full_name="پس از تغییر", org_unit="واحد طرح")
    make_access(db_session, other, org["sup"], org["dep"], org["ceo"])
    db_session.commit()

    record_id = _finalize(
        client, db_session, **{k: org[k] for k in ("hr", "sup", "dep", "ceo")},
        personnel=other, score=4,
    )
    record = db_session.get(EvaluationRecord, record_id)
    db_session.refresh(record)

    # نمرهٔ ۴ از ۵ ⇒ ۸۰٪. زیر جدول تازه (مرز ۹۵) این «نیازمند بازنگری» است،
    # در حالی که زیر جدول پایه «تمدید با شرایط استاندارد» بود.
    assert record.recommendation == "نیازمند بازنگری"
    assert record.scoring_scheme_id == scheme_id


# ── فعال‌سازی دو نفره ───────────────────────────────────────────────────────

def test_the_author_of_a_scheme_cannot_activate_it(client, org):
    """تغییر قاعدهٔ نمره‌دهیِ کل سازمان نباید تصمیم یک نفرِ تنها باشد."""
    scheme_id = _draft(client, org["hr"]).json()["id"]

    response = client.post(
        f"/api/scoring-schemes/{scheme_id}/activate", headers=auth_header(org["hr"])
    )

    assert response.status_code == 403
    assert "کاربر دیگری" in response.json()["detail"]


def test_a_second_hr_user_can_activate_it(client, org):
    scheme_id = _draft(client, org["hr"]).json()["id"]
    response = client.post(
        f"/api/scoring-schemes/{scheme_id}/activate", headers=auth_header(org["hr2"])
    )
    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert response.json()["activated_by_username"] == org["hr2"].username


def test_activation_retires_the_previous_scheme(client, db_session, org):
    """حداکثر یک طرح فعال — و ایندکس یکتای جزئی هم همین را تضمین می‌کند."""
    scheme_id = _draft(client, org["hr"]).json()["id"]
    client.post(f"/api/scoring-schemes/{scheme_id}/activate", headers=auth_header(org["hr2"]))

    body = client.get("/api/scoring-schemes", headers=auth_header(org["hr"])).json()
    active = [s for s in body if s["status"] == "active"]
    assert len(active) == 1
    assert active[0]["id"] == scheme_id
    assert next(s for s in body if s["version"] == 1)["status"] == "retired"


def test_only_hr_can_touch_schemes(client, org):
    for actor in ("sup", "dep", "ceo"):
        assert client.get(
            "/api/scoring-schemes", headers=auth_header(org[actor])
        ).status_code == 403
        assert _draft(client, org[actor]).status_code == 403


# ── تغییرناپذیری ────────────────────────────────────────────────────────────

def test_an_active_scheme_cannot_be_deleted(client, db_session, org):
    """نسخهٔ فعال یا بازنشسته سند تاریخ است: پرونده‌ها به آن مهر خورده‌اند و
    بدون آن دیگر نمی‌شود گفت با چه قواعدی حساب شده‌اند."""
    # select(ScoringScheme) و نه __table__.select(): دومی با db.scalar فقط
    # ستون اول را برمی‌گرداند، نه شیء را.
    from sqlalchemy import select

    base = db_session.scalar(select(ScoringScheme).where(ScoringScheme.version == 1))
    response = client.delete(
        f"/api/scoring-schemes/{base.id}", headers=auth_header(org["hr"])
    )
    assert response.status_code == 400


def test_a_draft_can_be_deleted(client, org):
    scheme_id = _draft(client, org["hr"]).json()["id"]
    assert client.delete(
        f"/api/scoring-schemes/{scheme_id}", headers=auth_header(org["hr"])
    ).status_code == 204


def test_an_activated_scheme_cannot_be_activated_again(client, org):
    scheme_id = _draft(client, org["hr"]).json()["id"]
    client.post(f"/api/scoring-schemes/{scheme_id}/activate", headers=auth_header(org["hr2"]))

    again = client.post(
        f"/api/scoring-schemes/{scheme_id}/activate", headers=auth_header(org["hr"])
    )
    assert again.status_code == 400


# ── اعتبارسنجی ورودی ───────────────────────────────────────────────────────

def test_section_weights_must_sum_to_one(client, org):
    """با ۰٫۶+۰٫۳ سقف واقعی ۹۰ می‌شود و هیچ‌کس به بالاترین پله نمی‌رسد — یک
    خرابیِ ساکت که فقط ماه‌ها بعد در آمار دیده می‌شود."""
    response = _draft(client, org["hr"], general_section_weight=0.6, specialized_section_weight=0.3)
    assert response.status_code == 422
    assert "مجموع وزن دو بخش" in response.json()["detail"]


def test_the_last_band_must_reach_above_one_hundred(client, org):
    """با سقف ۱۰۰، نمرهٔ کاملِ ۱۰۰ به هیچ برچسبی نمی‌رسد."""
    response = _draft(
        client,
        org["hr"],
        thresholds=[{"upper_exclusive": 60, "label": "الف"}, {"upper_exclusive": 100, "label": "ب"}],
    )
    assert response.status_code == 422
    assert "۱۰۰" in response.json()["detail"]


def test_bands_must_ascend(client, org):
    response = _draft(
        client,
        org["hr"],
        thresholds=[{"upper_exclusive": 90, "label": "الف"}, {"upper_exclusive": 60, "label": "ب"}],
    )
    assert response.status_code == 422
    assert "صعودی" in response.json()["detail"]


def test_min_words_cannot_exceed_max(client, org):
    response = _draft(client, org["hr"], evidence_min_words=50, evidence_max_words=10)
    assert response.status_code == 422


# ── پیش‌نمایش ──────────────────────────────────────────────────────────────

def test_the_preview_writes_nothing(client, db_session, org):
    _finalize(client, db_session, **{k: org[k] for k in ("hr", "sup", "dep", "ceo")},
              personnel=org["person"])
    db_session.expire_all()
    before = db_session.query(ScoringScheme).count()

    response = client.post(
        "/api/scoring-schemes/preview", json=STRICTER, headers=auth_header(org["hr"])
    )

    assert response.status_code == 200
    assert db_session.query(ScoringScheme).count() == before


def test_the_preview_shows_which_cases_change_label(client, db_session, org):
    """«۰٫۷ به‌جای ۰٫۶» یک عدد است؛ «این پرونده‌ها برچسبشان عوض می‌شود» یک تصمیم."""
    _finalize(client, db_session, **{k: org[k] for k in ("hr", "sup", "dep", "ceo")},
              personnel=org["person"], score=4)
    db_session.expire_all()

    body = client.post(
        "/api/scoring-schemes/preview", json=STRICTER, headers=auth_header(org["hr"])
    ).json()

    assert body["sample_size"] >= 1
    assert body["changed_count"] >= 1
    changed = next(c for c in body["cases"] if c["proposed_recommendation"] == "نیازمند بازنگری")
    assert changed["current_recommendation"] != changed["proposed_recommendation"]
    assert body["transitions"], "خلاصهٔ جابه‌جایی‌ها باید پر باشد"


def test_the_preview_names_no_individual(client, db_session, org):
    """پیش‌نمایش دربارهٔ *قاعده* است، نه دربارهٔ افراد. نام فرد آن‌جا نه لازم است
    نه بی‌خطر — این صفحه ممکن است روی پروژکتور یک جلسه باز شود."""
    _finalize(client, db_session, **{k: org[k] for k in ("hr", "sup", "dep", "ceo")},
              personnel=org["person"])
    db_session.expire_all()

    raw = client.post(
        "/api/scoring-schemes/preview", json=STRICTER, headers=auth_header(org["hr"])
    ).text

    assert "موضوع طرح" not in raw
    assert "full_name" not in raw


def test_a_preview_identical_to_the_active_scheme_changes_nothing(client, db_session, org):
    """اگر پیش‌نمایش با قواعد فعلی هم چیزی را «عوض‌شده» نشان بدهد، یعنی مسیر
    پیش‌نمایش و مسیر محاسبهٔ واقعی از هم جدا شده‌اند."""
    _finalize(client, db_session, **{k: org[k] for k in ("hr", "sup", "dep", "ceo")},
              personnel=org["person"])
    db_session.expire_all()
    base = client.get("/api/scoring-schemes", headers=auth_header(org["hr"])).json()[-1]

    body = client.post(
        "/api/scoring-schemes/preview",
        json={
            "name": "همان قواعد",
            "general_section_weight": base["general_section_weight"],
            "specialized_section_weight": base["specialized_section_weight"],
            "evidence_required_scores": base["evidence_required_scores"],
            "evidence_min_words": base["evidence_min_words"],
            "evidence_max_words": base["evidence_max_words"],
            "thresholds": base["thresholds"],
            "indicator_weights": {},
        },
        headers=auth_header(org["hr"]),
    ).json()

    assert body["changed_count"] == 0
    assert body["cases"] == []


# ── وزن شاخص ───────────────────────────────────────────────────────────────

def test_indicator_weights_shift_the_result(client, db_session, org):
    """یک شاخصِ سنگین باید نتیجه را جابه‌جا کند — و سقف بخش هم باید وزنی شود،
    وگرنه درصد از ۱۰۰ بالاتر می‌رود."""
    indicators = active_indicators(db_session)
    general = [i for i in indicators if i.section.value == "general"]
    scores = [
        {**row, "score": 5 if row["indicator_id"] == general[0].id else 3}
        for row in full_valid_scores(indicators)
    ]

    from app.services.evaluation import compute_result
    from app.services.scoring_scheme import LEGACY_RULES, Rules

    by_id = {i.id: i for i in indicators}
    flat = compute_result(scores, by_id, LEGACY_RULES)
    weighted = compute_result(
        scores,
        by_id,
        Rules(
            general_section_weight=LEGACY_RULES.general_section_weight,
            specialized_section_weight=LEGACY_RULES.specialized_section_weight,
            evidence_required_scores=LEGACY_RULES.evidence_required_scores,
            evidence_min_words=LEGACY_RULES.evidence_min_words,
            evidence_max_words=LEGACY_RULES.evidence_max_words,
            thresholds=LEGACY_RULES.thresholds,
            indicator_weights={general[0].id: 10.0},
        ),
    )

    assert weighted["general_score_pct"] > flat["general_score_pct"]
    assert weighted["general_score_pct"] <= 100, "سقف بخش باید وزنی باشد"


def test_the_config_endpoint_follows_the_active_scheme(client, org):
    """فرم امتیازدهی قاعدهٔ شواهد را از این می‌خواند. اگر عقب بماند، کاربر تیک
    سبز می‌گیرد و بعد سرور ثبت را رد می‌کند."""
    scheme_id = _draft(client, org["hr"]).json()["id"]
    client.post(f"/api/scoring-schemes/{scheme_id}/activate", headers=auth_header(org["hr2"]))

    config = client.get("/api/config", headers=auth_header(org["sup"])).json()
    assert config["evidence_min_words"] == STRICTER["evidence_min_words"]
    assert config["evidence_required_scores"] == STRICTER["evidence_required_scores"]


def test_the_activation_is_recorded_in_the_audit_log(client, org):
    scheme_id = _draft(client, org["hr"]).json()["id"]
    client.post(f"/api/scoring-schemes/{scheme_id}/activate", headers=auth_header(org["hr2"]))

    events = client.get(
        "/api/audit-log", params={"limit": 50}, headers=auth_header(org["hr"])
    ).json()["items"]
    entry = next(e for e in events if e["event_type"] == "scoring_scheme_activated")

    assert entry["new_value"]["version"] == 2
    assert entry["old_value"]["version"] == 1
    # چه کسی نوشت و چه کسی فعال کرد — هر دو باید بعداً قابل بازخوانی باشند
    assert entry["new_value"]["drafted_by_user_id"] == org["hr"].id


def test_finalised_scores_record_which_scheme_computed_them(client, db_session, org):
    record_id = _finalize(client, db_session, **{k: org[k] for k in ("hr", "sup", "dep", "ceo")},
                          personnel=org["person"])

    events = client.get(
        "/api/audit-log", params={"limit": 50}, headers=auth_header(org["hr"])
    ).json()["items"]
    entry = next(
        e for e in events
        if e["event_type"] == "score_submitted" and e["evaluation_record_id"] == record_id
    )
    assert entry["new_value"]["scheme_version"] == 1
