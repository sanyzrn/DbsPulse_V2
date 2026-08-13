"""ساخت حساب کاربری کارمند هم‌زمان با ثبت پرسنل.

پیش از این، دسترسی دادن به یک کارمند سه کار جدا بود: ثبت پرسنل، ساخت کاربر، و
لینک‌کردن این دو. مرحلهٔ دوم و سوم به‌سادگی فراموش می‌شد و نتیجه‌اش کارمندی بود که
هیچ راهی برای دیدن کارنامهٔ خودش نداشت — همان چیزی که کل مرحلهٔ «صدای کارمند» به آن
وابسته است.
"""
from sqlalchemy import select

from app.models.enums import UserRole
from app.models.personnel import Personnel
from app.models.user import User
from tests.helpers import auth_header, make_user

_PERSONNEL = {
    "personnel_code": "P-ACC-1",
    "full_name": "سارا احمدی",
    "job_title": "کارشناس",
    "org_unit": "واحد تست",
    "contract_start_date": "2025-01-01",
    "contract_end_date": "2026-01-01",
}


def _payload(**overrides) -> dict:
    body = dict(_PERSONNEL)
    body.update(overrides)
    return body


def test_personnel_and_account_are_created_together(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()

    r = client.post(
        "/api/personnel",
        json=_payload(account={"username": "sara.ahmadi", "password": "Temp-Pass-12345"}),
        headers=auth_header(hr),
    )

    assert r.status_code == 201
    assert r.json()["account_username"] == "sara.ahmadi"

    user = db_session.scalar(select(User).where(User.username == "sara.ahmadi"))
    personnel = db_session.scalar(select(Personnel).where(Personnel.personnel_code == "P-ACC-1"))
    assert user.personnel_id == personnel.id
    assert user.role == UserRole.employee, "این مسیر فقط برای دسترسی فرد به کارنامهٔ خودش است"
    assert user.is_active is True


def test_the_temporary_password_must_be_changed_on_first_use(client, db_session):
    """رمزی که HR تعیین می‌کند موقتی است — و از فاز ۰ این در بک‌اند اعمال می‌شود."""
    hr = make_user(db_session, "hr")
    db_session.commit()
    client.post(
        "/api/personnel",
        json=_payload(account={"username": "temp.user", "password": "Temp-Pass-12345"}),
        headers=auth_header(hr),
    )

    login = client.post(
        "/api/auth/login", json={"username": "temp.user", "password": "Temp-Pass-12345"}
    )
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True

    token = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/me/evaluations", headers=token).status_code == 403


def test_omitting_the_account_creates_personnel_only(client, db_session):
    """هر پرسنلی حساب لازم ندارد؛ حسابِ خفته با رمز موقتِ تغییرنکرده خودش یک بدهی است."""
    hr = make_user(db_session, "hr")
    db_session.commit()

    r = client.post("/api/personnel", json=_payload(personnel_code="P-ACC-2"), headers=auth_header(hr))

    assert r.status_code == 201
    assert r.json()["account_username"] is None
    personnel_id = r.json()["id"]
    assert db_session.scalar(select(User).where(User.personnel_id == personnel_id)) is None


def test_a_duplicate_username_is_rejected_before_anything_is_written(client, db_session):
    """اعتبارسنجی نام کاربری *پیش از* اولین نوشتن انجام می‌شود.

    اتمی‌بودن در production از خود تراکنش می‌آید (خطا یعنی commit اجرا نمی‌شود و
    session بسته می‌شود)، ولی ترتیب هم مهم است: بررسی زودهنگام یعنی HR یک خطای
    دقیق می‌گیرد، نه یک شکست مبهم بعد از نیمه‌کاره ماندن کار. این تست همان ترتیب
    را قفل می‌کند — با جابه‌جا کردن بررسی به بعد از INSERT، شکست می‌خورد.
    """
    hr = make_user(db_session, "hr")
    taken = make_user(db_session, "unit_supervisor")
    db_session.commit()

    r = client.post(
        "/api/personnel",
        json=_payload(personnel_code="P-ACC-3", account={"username": taken.username, "password": "Temp-Pass-12345"}),
        headers=auth_header(hr),
    )

    assert r.status_code == 400
    assert "نام کاربری" in r.json()["detail"]
    assert db_session.scalar(
        select(Personnel).where(Personnel.personnel_code == "P-ACC-3")
    ) is None, "وقتی حساب ساخته نشد، پرسنل هم نباید بماند"


def test_a_duplicate_personnel_code_creates_no_user_either(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()
    client.post(
        "/api/personnel",
        json=_payload(personnel_code="P-ACC-4", account={"username": "first.one", "password": "Temp-Pass-12345"}),
        headers=auth_header(hr),
    )

    r = client.post(
        "/api/personnel",
        json=_payload(personnel_code="P-ACC-4", account={"username": "second.one", "password": "Temp-Pass-12345"}),
        headers=auth_header(hr),
    )

    assert r.status_code == 400
    assert db_session.scalar(select(User).where(User.username == "second.one")) is None


def test_the_password_policy_is_the_same_one_used_for_users(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()

    r = client.post(
        "/api/personnel",
        json=_payload(personnel_code="P-ACC-5", account={"username": "weak.pass", "password": "short"}),
        headers=auth_header(hr),
    )

    assert r.status_code == 422


def test_the_username_pattern_is_the_same_one_used_for_users(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()

    r = client.post(
        "/api/personnel",
        json=_payload(personnel_code="P-ACC-6", account={"username": "نام فارسی", "password": "Temp-Pass-12345"}),
        headers=auth_header(hr),
    )

    assert r.status_code == 422


def test_account_creation_is_audited_with_the_link(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()
    client.post(
        "/api/personnel",
        json=_payload(personnel_code="P-ACC-7", account={"username": "audited.user", "password": "Temp-Pass-12345"}),
        headers=auth_header(hr),
    )

    events = client.get(
        "/api/audit-log", params={"event_type": "user_created"}, headers=auth_header(hr)
    ).json()
    rows = events["items"] if isinstance(events, dict) and "items" in events else events
    entry = next(r for r in rows if r["new_value"].get("username") == "audited.user")
    assert entry["new_value"]["created_with_personnel"] is True
    assert entry["new_value"]["personnel_id"]


def test_only_hr_can_create_personnel_with_an_account(client, db_session):
    supervisor = make_user(db_session, "unit_supervisor")
    db_session.commit()

    r = client.post(
        "/api/personnel",
        json=_payload(personnel_code="P-ACC-8", account={"username": "sneaky", "password": "Temp-Pass-12345"}),
        headers=auth_header(supervisor),
    )

    assert r.status_code == 403
    assert db_session.scalar(select(User).where(User.username == "sneaky")) is None
