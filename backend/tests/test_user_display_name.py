"""نامِ آدم، جدا از نام کاربری.

حساب‌های نقش‌دار — معاونت، مدیرعامل، مسئول واحد — پروندهٔ پرسنلی ندارند، پس تا
پیش از این همه‌جای سامانه با نام کاربری دیده می‌شدند: «dep1» پای تأیید یک
ارزیابی. آن رشته برای *ورود* ساخته شده، نه برای این‌که به کسی بگوید چه کسی
تصمیم گرفته.

سه ادعا این‌جا سنجیده می‌شود، و ترتیبشان مهم است:

۱. نام روی حساب ذخیره و برگردانده می‌شود.
۲. وقتی نامی نیست، `display_name` خالی نمی‌ماند — نام کاربری را می‌دهد.
۳. برای حسابِ وصل به پرسنل، مرجعِ نام پروندهٔ پرسنلی است. دو منبع حقیقت یعنی
   اصلاحِ نام در یکی، آن یکی را کهنه می‌گذارد.
"""
from app.models.enums import Capability
from tests.helpers import auth_header, make_personnel, make_user


def _admin(db_session):
    user = make_user(db_session, "hr")
    db_session.commit()
    return user


def test_name_round_trips_through_create(client, db_session):
    admin = _admin(db_session)
    response = client.post(
        "/api/users",
        json={
            "username": "dep2",
            "password": "Deputy-Two-2026",
            "role": "deputy",
            "full_name": "معاونت فنی، آقای رضایی",
        },
        headers=auth_header(admin),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["full_name"] == "معاونت فنی، آقای رضایی"
    assert body["display_name"] == "معاونت فنی، آقای رضایی"


def test_display_name_falls_back_to_username(client, db_session):
    """حسابِ بی‌نام نباید در UI یک خانهٔ خالی بشود."""
    admin = _admin(db_session)
    response = client.post(
        "/api/users",
        json={"username": "dep3", "password": "Deputy-Three-26", "role": "deputy"},
        headers=auth_header(admin),
    )
    assert response.status_code == 201, response.text
    assert response.json()["full_name"] is None
    assert response.json()["display_name"] == "dep3"


def test_personnel_name_wins_over_the_account_name(client, db_session):
    """پروندهٔ پرسنلی مرجع است.

    اگر نامِ روی حساب برنده می‌شد، HR می‌توانست نام یک نفر را در پرونده‌اش اصلاح
    کند و صفحهٔ کاربران تا ابد نام قدیمی را نشان بدهد.
    """
    admin = _admin(db_session)
    personnel = make_personnel(db_session, full_name="زهرا کریمی")
    db_session.commit()

    created = client.post(
        "/api/users",
        json={
            "username": "emp_karimi",
            "password": "Employee-2026-x",
            "role": "employee",
            "personnel_id": personnel.id,
            "full_name": "یک نام کهنه",
        },
        headers=auth_header(admin),
    )
    assert created.status_code == 201, created.text
    assert created.json()["display_name"] == "زهرا کریمی"


def test_search_finds_a_user_by_name_not_only_username(client, db_session):
    """کسی که دنبال «رضایی» می‌گردد نمی‌داند نام کاربری‌اش dep4 است."""
    admin = _admin(db_session)
    client.post(
        "/api/users",
        json={
            "username": "dep4",
            "password": "Deputy-Four-26",
            "role": "deputy",
            "full_name": "معاونت اداری، آقای رضایی",
        },
        headers=auth_header(admin),
    )
    found = client.get("/api/users", params={"q": "رضایی"}, headers=auth_header(admin))
    assert found.status_code == 200, found.text
    assert [u["username"] for u in found.json()["items"]] == ["dep4"]


def test_audit_log_names_the_actor(client, db_session):
    """لاگ حسابرسی هر دو را می‌دهد: کدام حساب، و کدام آدم."""
    admin = make_user(
        db_session,
        "hr",
        capabilities=[Capability.manage_users, Capability.view_audit_log],
    )
    admin.full_name = "منابع انسانی، خانم کریمی"
    db_session.commit()

    client.post(
        "/api/users",
        json={"username": "dep5", "password": "Deputy-Five-26", "role": "deputy"},
        headers=auth_header(admin),
    )
    entries = client.get(
        "/api/audit-log", params={"event_type": "user_created"}, headers=auth_header(admin)
    )
    assert entries.status_code == 200, entries.text
    row = entries.json()["items"][0]
    assert row["actor_username"] == admin.username
    assert row["actor_display_name"] == "منابع انسانی، خانم کریمی"


def test_me_reports_the_personnel_name(client, db_session):
    """نوار بالای صفحه برای کارمند، نام خودش را نشان می‌دهد نه نام کاربری‌اش."""
    personnel = make_personnel(db_session, full_name="علی محمدی")
    employee = make_user(db_session, "employee", personnel_id=personnel.id, capabilities=[])
    db_session.commit()

    response = client.get("/api/auth/me", headers=auth_header(employee))
    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == "علی محمدی"


def test_renaming_an_account_needs_the_user_management_capability(client, db_session):
    """نام هم یک تغییر اداری است، نه یک فیلد بی‌صاحب.

    بدون این، حسابی که عمداً مجوز مدیریت کاربران ندارد می‌توانست نامی را عوض
    کند که در لاگ حسابرسی پای تصمیم‌ها می‌نشیند.
    """
    powerless = make_user(db_session, "hr", capabilities=[Capability.view_diagnostics])
    target = make_user(db_session, "deputy", capabilities=[])
    db_session.commit()

    response = client.patch(
        f"/api/users/{target.id}",
        json={"full_name": "یک نام تازه"},
        headers=auth_header(powerless),
    )
    assert response.status_code == 403, response.text
