"""P1-05 — ویرایش شاخص‌ها نباید معنای گذشته را بازنویسی کند یا پرونده‌های باز را بشکند.

دو خرابیِ جدا، که هیچ‌کدام برای کسی که ویرایش می‌کند دیده نمی‌شوند:

۱. **عملیاتی.** افزودن یا غیرفعال‌کردن یک شاخص وسط چرخه، هر پیش‌نویسِ در جریان را
   غیرقابل‌ثبت می‌کند — چون «کامل بودن» با مجموعهٔ *فعالِ امروز* سنجیده می‌شود، نه
   با آنچه ارزیاب جلویش داشته.
۲. **تحلیلی.** متن شاخص درجا قابل بازنویسی است، پس نموداری که «شاخص ۷» را در دو
   سال مقایسه می‌کند ممکن است دو سؤال متفاوت را کنار هم گذاشته باشد.

این فایل اول هر دو را *بازتولید* می‌کند، بعد رفتار درست را می‌سنجد.
"""
import pytest

from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


@pytest.fixture()
def chain(db_session):
    """یک زنجیرهٔ کامل با پرسنل — پایهٔ همهٔ سناریوهای این فایل."""
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    person = make_personnel(db_session, full_name="سوژهٔ چارچوب")
    make_access(db_session, person, sup, dep, ceo)
    db_session.commit()
    return {"hr": hr, "sup": sup, "dep": dep, "ceo": ceo, "person": person}


def _open_and_score(client, db_session, chain):
    """پرونده‌ای که ارزیاب کاملاً پرش کرده و هنوز ثبت نکرده — پیش‌نویسِ در جریان."""
    record_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": chain["person"].id},
        headers=auth_header(chain["sup"]),
    ).json()["id"]
    response = client.put(
        f"/api/evaluations/{record_id}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(chain["sup"]),
    )
    assert response.status_code == 200
    return record_id


def test_adding_an_indicator_does_not_break_a_draft_in_flight(client, db_session, chain):
    """کارِ اصلی این تغییر.

    ارزیاب فرم را کامل پر کرده و رفته. منابع انسانی یک سؤال تازه اضافه می‌کند.
    فردا که ارزیاب برمی‌گردد و «ثبت» می‌زند، نباید با «به تمام شاخص‌ها امتیاز
    بدهید» روبه‌رو شود برای سؤالی که اصلاً وجود نداشت.
    """
    record_id = _open_and_score(client, db_session, chain)

    created = client.post(
        "/api/indicators",
        json={
            "section": "general",
            "category": "تازه",
            "description": "سؤالی که بعد از باز شدن پرونده اضافه شد",
            "display_order": 99,
        },
        headers=auth_header(chain["hr"]),
    )
    assert created.status_code == 201

    submitted = client.post(
        f"/api/evaluations/{record_id}/submit", headers=auth_header(chain["sup"])
    )
    assert submitted.status_code == 200, submitted.text


def test_deactivating_an_indicator_does_not_break_a_draft_in_flight(client, db_session, chain):
    """و همین‌طور جهت مخالف: حذف سؤالی که ارزیاب قبلاً به آن نمره داده."""
    record_id = _open_and_score(client, db_session, chain)
    victim = active_indicators(db_session)[0]

    client.patch(
        f"/api/indicators/{victim.id}",
        json={"is_active": False},
        headers=auth_header(chain["hr"]),
    )

    submitted = client.post(
        f"/api/evaluations/{record_id}/submit", headers=auth_header(chain["sup"])
    )
    assert submitted.status_code == 200, submitted.text


def test_a_half_filled_draft_can_still_be_saved_after_the_question_is_retired(
    client, db_session, chain
):
    """ذخیرهٔ خودکارِ فرم هم نباید بشکند.

    اگر فقط «ثبت» را درست می‌کردیم و ذخیره را نه، ارزیاب هر بار که چیزی تایپ
    می‌کرد یک ۴۰۰ می‌گرفت و کار نیمه‌تمامش از دست می‌رفت — یعنی همان خرابی، فقط
    دردناک‌تر.
    """
    record_id = _open_and_score(client, db_session, chain)
    indicators = active_indicators(db_session)
    client.patch(
        f"/api/indicators/{indicators[0].id}",
        json={"is_active": False},
        headers=auth_header(chain["hr"]),
    )

    resaved = client.put(
        f"/api/evaluations/{record_id}/scores",
        json={"scores": full_valid_scores(indicators)},
        headers=auth_header(chain["sup"]),
    )
    assert resaved.status_code == 200, resaved.text


def test_a_brand_new_case_gets_the_new_questions(client, db_session, chain):
    """پایداری برای پروندهٔ باز، تازگی برای پروندهٔ تازه — هر دو با هم.

    اگر فقط نیمهٔ اول را می‌ساختیم، شاخص تازه هرگز به هیچ پرونده‌ای نمی‌رسید.
    """
    _open_and_score(client, db_session, chain)
    client.post(
        "/api/indicators",
        json={"section": "general", "category": "تازه", "description": "سؤال تازه", "display_order": 99},
        headers=auth_header(chain["hr"]),
    )

    other = make_personnel(db_session, full_name="نفر دوم")
    make_access(db_session, other, chain["sup"], chain["dep"], chain["ceo"])
    db_session.commit()
    new_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": other.id},
        headers=auth_header(chain["sup"]),
    ).json()["id"]

    detail = client.get(f"/api/evaluations/{new_id}", headers=auth_header(chain["sup"])).json()
    fresh_ids = set(detail["indicator_ids"])
    assert len(fresh_ids) == len(active_indicators(db_session))
    assert detail["indicator_framework_version"] == 2


def test_an_untouched_open_case_moves_to_the_new_questions(client, db_session, chain):
    """پرونده‌ای که هیچ‌کس دستش نزده باید سؤال‌های امروز را بپرسد.

    بی‌خطر است *دقیقاً چون* امتیازی وجود ندارد که بشکند — و اگر منتقل نمی‌شد،
    منابع انسانی سؤالی اضافه می‌کرد و روی پرونده‌های تازه‌بازشده نمی‌دید.
    """
    record_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": chain["person"].id},
        headers=auth_header(chain["sup"]),
    ).json()["id"]
    before = client.get(
        f"/api/evaluations/{record_id}", headers=auth_header(chain["sup"])
    ).json()["indicator_framework_version"]

    client.post(
        "/api/indicators",
        json={"section": "general", "category": "تازه", "description": "سؤال تازه", "display_order": 99},
        headers=auth_header(chain["hr"]),
    )

    after = client.get(f"/api/evaluations/{record_id}", headers=auth_header(chain["sup"])).json()
    assert after["indicator_framework_version"] == before + 1
    assert len(after["indicator_ids"]) == len(active_indicators(db_session))


def test_a_finalized_case_is_never_rebound(client, db_session, chain):
    """و پروندهٔ بسته‌شده تحت هیچ شرایطی جابه‌جا نمی‌شود.

    سند رسمی صادر شده؛ عوض‌کردن «چه سؤالی پرسیده شد» بعد از آن، بازنویسی تاریخ
    است حتی اگر هیچ نمره‌ای عوض نشود.
    """
    record_id = _open_and_score(client, db_session, chain)
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(chain["sup"]))
    client.post(f"/api/evaluations/{record_id}/hr-approve", headers=auth_header(chain["hr"]))
    client.post(f"/api/evaluations/{record_id}/deputy-approve", headers=auth_header(chain["dep"]))
    client.post(f"/api/evaluations/{record_id}/ceo-finalize", headers=auth_header(chain["ceo"]))

    sealed = client.get(f"/api/evaluations/{record_id}", headers=auth_header(chain["hr"])).json()
    client.post(
        "/api/indicators",
        json={"section": "general", "category": "تازه", "description": "سؤال تازه", "display_order": 99},
        headers=auth_header(chain["hr"]),
    )

    after = client.get(f"/api/evaluations/{record_id}", headers=auth_header(chain["hr"])).json()
    assert after["indicator_framework_version"] == sealed["indicator_framework_version"]


# ── معنا در برابر نگارش ─────────────────────────────────────────────────────

def test_rewriting_a_scored_indicator_is_refused_without_a_declaration(client, db_session, chain):
    """خرابی دوم: بازنویسی درجای متن، معنای گذشته را عوض می‌کند.

    سامانه نمی‌تواند «غلط املایی را درست کردم» را از «سؤال را عوض کردم» جدا کند.
    پس حدس نمی‌زند — از کسی که تایپ می‌کند می‌پرسد، چون تنها او می‌داند.
    """
    _open_and_score(client, db_session, chain)
    target = active_indicators(db_session)[0]

    refused = client.patch(
        f"/api/indicators/{target.id}",
        json={"description": "یک سؤال کاملاً متفاوت"},
        headers=auth_header(chain["hr"]),
    )
    assert refused.status_code == 409
    assert "جایگزین" in refused.json()["detail"]

    db_session.expire_all()
    assert db_session.get(type(target), target.id).description == target.description


def test_a_declared_wording_fix_goes_through_and_is_recorded(client, db_session, chain):
    """و اصلاح نگارشی مسدود نمی‌شود — فقط ادعایش ثبت می‌شود.

    اگر بستنِ راه ساده‌ترین کار بود، منابع انسانی برای اصلاح یک غلط املایی مجبور
    می‌شد شاخص را جایگزین کند و تاریخچه پر از شاخص‌های تکراری می‌شد.
    """
    _open_and_score(client, db_session, chain)
    target = active_indicators(db_session)[0]

    fixed = client.patch(
        f"/api/indicators/{target.id}",
        json={
            "description": f"{target.description} ",
            "category": "همکاری با همکاران",
            "wording_fix_reason": "غلط املایی در عنوان دسته",
        },
        headers=auth_header(chain["hr"]),
    )
    assert fixed.status_code == 200
    assert fixed.json()["category"] == "همکاری با همکاران"

    events = client.get(
        "/api/audit-log", params={"limit": 50}, headers=auth_header(chain["hr"])
    ).json()["items"]
    entry = next(e for e in events if e["event_type"] == "indicator_updated")
    assert entry["new_value"]["wording_fix_reason"] == "غلط املایی در عنوان دسته"


def test_an_unscored_indicator_is_still_freely_editable(client, db_session, chain):
    """شاخصی که هنوز به کسی نمره نداده، تاریخی ندارد که بشکند.

    گاردی که همیشه روشن باشد، کارِ عادیِ ستون‌بندی فرم را هم سخت می‌کند و
    مردم یاد می‌گیرند دورش بزنند.
    """
    fresh = client.post(
        "/api/indicators",
        json={"section": "general", "category": "الف", "description": "ب", "display_order": 99},
        headers=auth_header(chain["hr"]),
    ).json()

    edited = client.patch(
        f"/api/indicators/{fresh['id']}",
        json={"description": "متن کاملاً عوض‌شده"},
        headers=auth_header(chain["hr"]),
    )
    assert edited.status_code == 200


def test_replacing_keeps_the_old_id_pointing_at_the_old_question(client, db_session, chain):
    """راهِ درستِ عوض‌کردن معنا: شناسهٔ تازه.

    این تنها چیزی است که تحلیل می‌تواند به آن اعتماد کند — اگر معنای یک شناسه
    هرگز عوض نشود، نموداری که بر اساس شناسه گروه می‌کند هیچ‌وقت دو سؤال متفاوت
    را یکی نمی‌بیند.
    """
    record_id = _open_and_score(client, db_session, chain)
    old = active_indicators(db_session)[0]
    old_text = old.description

    created = client.post(
        f"/api/indicators/{old.id}/replace",
        json={
            "category": old.category,
            "description": "سنجهٔ تازه با معنای متفاوت",
            "reason": "سؤال قبلی دو مفهوم را با هم می‌پرسید",
        },
        headers=auth_header(chain["hr"]),
    )
    assert created.status_code == 201
    replacement = created.json()
    assert replacement["id"] != old.id
    assert replacement["display_order"] == old.display_order

    # شاخص قدیمی هنوز همان سؤال قدیمی است
    db_session.expire_all()
    stale = db_session.get(type(old), old.id)
    assert stale.description == old_text
    assert stale.is_active is False

    # و پروندهٔ در جریان هنوز به همان سؤال قدیمی نمره می‌دهد
    detail = client.get(f"/api/evaluations/{record_id}", headers=auth_header(chain["sup"])).json()
    assert old.id in detail["indicator_ids"]
    assert replacement["id"] not in detail["indicator_ids"]


def test_the_impact_preview_separates_frozen_from_movable(client, db_session, chain):
    """آنچه منابع انسانی باید *قبل از* کلیک بداند.

    تا امروز نمی‌دانست، و چون خرابی هم بی‌صدا بود، معمولاً اولین کسی که می‌فهمید
    ارزیابی بود که فردا «ثبت»‌اش کار نمی‌کرد.
    """
    _open_and_score(client, db_session, chain)  # امتیاز خورده → منجمد
    other = make_personnel(db_session, full_name="دست‌نخورده")
    make_access(db_session, other, chain["sup"], chain["dep"], chain["ceo"])
    db_session.commit()
    client.post(
        "/api/evaluations",
        json={"subject_personnel_id": other.id},
        headers=auth_header(chain["sup"]),
    )  # بدون امتیاز → قابل انتقال

    impact = client.get("/api/indicators/framework", headers=auth_header(chain["hr"])).json()

    assert impact["frozen_open_records"] == 1
    assert impact["movable_open_records"] == 1
    assert impact["member_count"] == len(active_indicators(db_session))
