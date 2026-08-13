"""اعلان‌ها نباید به آدم اشتباه برسند.

گزارش شده بود که در تست‌های دستی، اعلانی مربوط به پروندهٔ یک کارمند به حساب دیگری
رسیده است. بازرسی چشمی کد کافی نیست — این تست دو زنجیرهٔ ارزیابی کاملاً مجزا با
بازیگرانِ بدون هم‌پوشانی می‌سازد، کل گردش‌کار را روی هر دو اجرا می‌کند، و بعد ثابت
می‌کند هیچ بازیگرِ زنجیرهٔ اول اعلانی دربارهٔ پروندهٔ زنجیرهٔ دوم نگرفته است.
"""
from sqlalchemy import select

from app.models.evaluation import EvaluationRecord
from app.models.notification import Notification
from app.models.user import User
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


def _isolated_chain(client, db_session, org_unit: str):
    """یک پرونده با مجموعهٔ بازیگرانِ کاملاً اختصاصی — هیچ کاربری بین دو زنجیره مشترک نیست.

    نام پرسنل هم عمداً یکتاست: هلپر مشترک به همه «کارمند تست» می‌دهد، و با نام
    یکسان نمی‌شود ثابت کرد متن یک اعلان به کدام پرونده اشاره دارد.
    """
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(
        db_session, org_unit=org_unit, full_name=f"کارمند {org_unit}"
    )
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
    client.post(f"/api/evaluations/{evaluation['id']}/hr-approve", headers=auth_header(hr))
    client.post(f"/api/evaluations/{evaluation['id']}/deputy-approve", headers=auth_header(dep))
    client.post(f"/api/evaluations/{evaluation['id']}/ceo-finalize", headers=auth_header(ceo))

    return {
        "id": evaluation["id"],
        "code": evaluation["evaluation_code"],
        "personnel": personnel,
        "hr": hr,
        "sup": sup,
        "dep": dep,
        "ceo": ceo,
        "employee": employee,
    }


def _notifications_of(db_session, user: User) -> list[Notification]:
    return list(
        db_session.scalars(select(Notification).where(Notification.user_id == user.id))
    )


def test_no_actor_of_one_case_hears_about_the_other(client, db_session):
    """ادعای اصلی: بازیگرانِ زنجیرهٔ الف هیچ اعلانی دربارهٔ پروندهٔ ب نمی‌گیرند."""
    first = _isolated_chain(client, db_session, "واحد الف")
    second = _isolated_chain(client, db_session, "واحد ب")

    for role in ("sup", "dep", "ceo", "employee"):
        for note in _notifications_of(db_session, first[role]):
            assert note.evaluation_record_id != second["id"], (
                f"{role} زنجیرهٔ اول، اعلانی دربارهٔ پروندهٔ زنجیرهٔ دوم گرفت: {note.message}"
            )
            assert second["code"] not in (note.message or ""), (
                f"{role} زنجیرهٔ اول، کد پروندهٔ زنجیرهٔ دوم را در متن اعلان دید"
            )
            assert second["personnel"].full_name not in (note.message or ""), (
                f"{role} زنجیرهٔ اول، نام پرسنلِ زنجیرهٔ دوم را در متن اعلان دید"
            )


def test_an_employee_only_ever_hears_about_their_own_record(client, db_session):
    """کارمند حساس‌ترین حالت است: فقط باید نتیجهٔ پروندهٔ خودش را ببیند."""
    first = _isolated_chain(client, db_session, "واحد ج")
    second = _isolated_chain(client, db_session, "واحد د")

    for chain, other in ((first, second), (second, first)):
        notes = _notifications_of(db_session, chain["employee"])
        assert notes, "کارمند باید از نهایی‌شدن پروندهٔ خودش باخبر شود"
        for note in notes:
            assert note.evaluation_record_id == chain["id"]
            assert other["personnel"].full_name not in (note.message or "")


def test_the_api_never_returns_another_users_notifications(client, db_session):
    """حتی اگر جایی اعلان اشتباه ساخته شود، endpoint نباید آن را به دیگری نشان دهد."""
    first = _isolated_chain(client, db_session, "واحد ه")
    second = _isolated_chain(client, db_session, "واحد و")

    body = client.get("/api/notifications", params={"limit": 100}, headers=auth_header(first["dep"])).json()
    rows = body["items"] if isinstance(body, dict) else body
    assert all(r["evaluation_record_id"] != second["id"] for r in rows)

    # و برعکس
    body = client.get("/api/notifications", params={"limit": 100}, headers=auth_header(second["dep"])).json()
    rows = body["items"] if isinstance(body, dict) else body
    assert all(r["evaluation_record_id"] != first["id"] for r in rows)


def test_reading_another_users_notification_is_refused(client, db_session):
    first = _isolated_chain(client, db_session, "واحد ز")
    second = _isolated_chain(client, db_session, "واحد ح")

    theirs = _notifications_of(db_session, second["dep"])
    assert theirs, "پیش‌فرض تست: معاونت زنجیرهٔ دوم باید اعلانی داشته باشد"

    r = client.post(
        f"/api/notifications/{theirs[0].id}/read", headers=auth_header(first["dep"])
    )
    assert r.status_code == 404, "علامت‌زدن اعلان دیگری نباید ممکن باشد"


def test_hr_hears_about_every_case_because_hr_owns_the_queue(client, db_session):
    """در مقابل: HR *باید* دربارهٔ همهٔ پرونده‌ها خبر بگیرد — این نشتی نیست، طراحی است.

    این تست وجود دارد تا اگر روزی کسی «اعلان‌های اضافهٔ HR» را ببندد، بداند دارد
    رفتار عمدی را عوض می‌کند.
    """
    first = _isolated_chain(client, db_session, "واحد ط")

    # HR زنجیرهٔ دوم هم دربارهٔ پروندهٔ اول خبر دارد، چون صف HR مشترک است
    second_hr = make_user(db_session, "hr")
    db_session.commit()
    third = _isolated_chain(client, db_session, "واحد ی")

    notes = _notifications_of(db_session, second_hr)
    assert any(n.evaluation_record_id == third["id"] for n in notes)
    assert first  # زنجیرهٔ اول فقط برای ساخت زمینه است


def test_a_returned_case_notifies_only_its_own_evaluator(client, db_session):
    """برگشت پرونده باید فقط به نمره‌دهندهٔ همان پرونده برود."""
    first = _isolated_chain(client, db_session, "واحد ک")
    second = _isolated_chain(client, db_session, "واحد ل")

    # یک پروندهٔ تازه در زنجیرهٔ دوم که بشود برش گرداند
    personnel = make_personnel(db_session, org_unit="واحد ل")
    make_access(db_session, personnel, second["sup"], second["dep"], second["ceo"])
    db_session.commit()
    evaluation = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(second["sup"])
    ).json()
    client.put(
        f"/api/evaluations/{evaluation['id']}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(second["sup"]),
    )
    client.post(f"/api/evaluations/{evaluation['id']}/submit", headers=auth_header(second["sup"]))
    client.post(
        f"/api/evaluations/{evaluation['id']}/return",
        json={"reason": "شواهد ناکافی"},
        headers=auth_header(second["hr"]),
    )

    for note in _notifications_of(db_session, first["sup"]):
        assert note.evaluation_record_id != evaluation["id"]


def test_every_notification_points_at_a_record_its_owner_may_view(client, db_session):
    """گارد کلی: برای هر اعلانِ گره‌خورده به یک پرونده، گیرنده باید حق دیدن آن را داشته باشد.

    این همان چیزی است که «اعلان مربوط به کارمند دیگر» را می‌گیرد، مستقل از این‌که
    از کدام مسیر ساخته شده باشد.
    """
    chains = [
        _isolated_chain(client, db_session, "واحد م"),
        _isolated_chain(client, db_session, "واحد ن"),
    ]

    for note in db_session.scalars(
        select(Notification).where(Notification.evaluation_record_id.is_not(None))
    ):
        record = db_session.get(EvaluationRecord, note.evaluation_record_id)
        recipient = db_session.get(User, note.user_id)
        if recipient.role.value == "hr":
            continue  # HR صف مشترک دارد و همهٔ پرونده‌ها را می‌بیند
        allowed = {
            record.unit_supervisor_user_id,
            record.deputy_user_id,
            record.ceo_user_id,
        }
        if recipient.role.value == "employee":
            assert recipient.personnel_id == record.subject_personnel_id, (
                f"کارمند #{recipient.id} اعلانی دربارهٔ پروندهٔ فرد دیگری گرفت: {note.message}"
            )
        else:
            assert recipient.id in allowed, (
                f"کاربر #{recipient.id} ({recipient.role.value}) اعلانی دربارهٔ پرونده‌ای "
                f"گرفت که در زنجیره‌اش نیست: {note.message}"
            )
    assert chains
